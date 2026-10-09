import os
from functools import partial
from typing import NoReturn

from django.db import transaction
from django.http import FileResponse
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle

from accounts.authentication import authenticated_user

from ..choices import (
    DataImportMode,
    DataTransferFormat,
    DataTransferJobType,
    DataTransferStatus,
)
from ..import_config import MAX_IMPORT_UPLOAD_BYTES, expected_formats_for_source, supported_import_sources
from ..import_errors import ImportDomainError, ImportErrorCode, raise_import_validation_error
from ..models import DataTransferJob
from ..serializers import DataTransferJobSerializer
from ..tasks.import_commands import ConfirmImportCommand


def _raise_import_error(code: str, message: str, field: str = 'job') -> NoReturn:
    raise_import_validation_error(ImportDomainError(code=code, message=message, field=field))


class DataImportView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = 'data_import'

    def post(self, request, *args, **kwargs):
        fmt = request.query_params.get('data_format', request.query_params.get('format', DataTransferFormat.ZIP)).lower()
        if fmt not in (DataTransferFormat.CSV, DataTransferFormat.ZIP):
            raise ValidationError({'format': 'format must be csv or zip'})
        source = (request.query_params.get('source') or '').strip().lower()
        uploaded = request.FILES.get('file')
        if not uploaded:
            raise ValidationError({'file': 'file is required'})
        if uploaded.size > MAX_IMPORT_UPLOAD_BYTES:
            raise ValidationError({'file': f'file must be at most {MAX_IMPORT_UPLOAD_BYTES // (1024 * 1024)} MB'})

        supported_sources = supported_import_sources()
        if not source:
            raise ValidationError({'source': f"source is required ({', '.join(supported_sources)})."})
        expected_formats = expected_formats_for_source(source)
        if expected_formats is None:
            raise ValidationError({'source': f"source must be {', '.join(supported_sources)}"})
        if fmt not in expected_formats:
            expected = ' or '.join(expected_formats)
            raise ValidationError({'format': f'format must be {expected} for source={source}.'})

        job = DataTransferJob.objects.create(
            user=authenticated_user(request),
            job_type=DataTransferJobType.IMPORT,
            data_format=fmt,
            status=DataTransferStatus.PENDING,
            input_file=uploaded,
            source=source,
            import_mode=DataImportMode.NEW_ITEMS,
        )

        from ..tasks import prepare_import_job

        transaction.on_commit(partial(prepare_import_job.delay, job.id))
        return Response(DataTransferJobSerializer(job, context={'request': request}).data, status=status.HTTP_201_CREATED)


class DataExportView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = 'data_export'

    def post(self, request, *args, **kwargs):
        fmt = request.query_params.get('data_format', request.query_params.get('format', DataTransferFormat.ZIP)).lower()
        if fmt != DataTransferFormat.ZIP:
            raise ValidationError({'format': 'format must be zip'})
        job = DataTransferJob.objects.create(
            user=request.user,
            job_type=DataTransferJobType.EXPORT,
            data_format=fmt,
            status=DataTransferStatus.PENDING,
        )
        from ..tasks import export_user_data
        transaction.on_commit(partial(export_user_data.delay, job.id))
        return Response(DataTransferJobSerializer(job, context={'request': request}).data, status=status.HTTP_201_CREATED)


class DataJobStatusView(generics.RetrieveAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataTransferJob.objects.filter(user=authenticated_user(self.request))


class DataJobListView(generics.ListAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataTransferJob.objects.filter(user=authenticated_user(self.request))


class DataJobConfirmView(generics.GenericAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = authenticated_user(request)
        try:
            pk = int(str(kwargs.get('pk')))
        except (TypeError, ValueError):
            _raise_import_error(ImportErrorCode.IMPORT_JOB_NOT_FOUND, 'Import job not found.')
        job = DataTransferJob.objects.filter(user=user, id=pk).first()
        if not job:
            _raise_import_error(ImportErrorCode.IMPORT_JOB_NOT_FOUND, 'Import job not found.')

        import_mode = (request.data.get('import_mode') or '').strip().lower()
        try:
            ConfirmImportCommand(job, import_mode).execute()
        except ImportDomainError as exc:
            raise_import_validation_error(exc)

        from ..tasks import run_import_job

        transaction.on_commit(partial(run_import_job.delay, job.id))
        serializer = self.get_serializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class DataJobCancelView(generics.GenericAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = authenticated_user(request)
        try:
            pk = int(str(kwargs.get('pk')))
        except (TypeError, ValueError):
            _raise_import_error(ImportErrorCode.IMPORT_JOB_NOT_FOUND, 'Import job not found.')
        job = DataTransferJob.objects.filter(user=user, id=pk).first()
        if not job:
            _raise_import_error(ImportErrorCode.IMPORT_JOB_NOT_FOUND, 'Import job not found.')
        from ..import_state_machine import cancel

        try:
            cancel(job)
        except ImportDomainError as exc:
            raise_import_validation_error(exc)
        return Response(self.get_serializer(job, context={'request': request}).data, status=status.HTTP_200_OK)


class DataJobFileView(generics.GenericAPIView):
    serializer_class = DataTransferJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _get_export_job(self, request, pk):
        # Scoped to the requesting user: nobody can access another user's file.
        user = authenticated_user(request)
        try:
            job_id = int(str(pk))
        except (TypeError, ValueError):
            _raise_import_error(ImportErrorCode.IMPORT_JOB_NOT_FOUND, 'Import job not found.')
        job = DataTransferJob.objects.filter(user=user, id=job_id).first()
        if not job:
            _raise_import_error(ImportErrorCode.IMPORT_JOB_NOT_FOUND, 'Import job not found.')
        if job.job_type != DataTransferJobType.EXPORT:
            raise ValidationError({'job': 'Only export jobs have a downloadable file.'})
        return job

    def get(self, request, *args, **kwargs):
        job = self._get_export_job(request, kwargs.get('pk'))
        if not job.output_file:
            raise NotFound('Export file not found.')
        try:
            handle = job.output_file.open('rb')
        except FileNotFoundError as exc:
            raise NotFound('Export file not found.') from exc
        response = FileResponse(handle, as_attachment=True, filename=os.path.basename(job.output_file.name))
        response['Cache-Control'] = 'private, no-store'
        return response

    def delete(self, request, *args, **kwargs):
        job = self._get_export_job(request, kwargs.get('pk'))
        if job.output_file:
            job.output_file.delete(save=False)
            job.output_file = None
            job.save(update_fields=['output_file', 'updated_at'])
        return Response(self.get_serializer(job, context={'request': request}).data, status=status.HTTP_200_OK)
