from rest_framework import serializers

MINIMUM_AVAILABILITY_CHOICES = ['announced', 'inCinemas', 'released']


class RadarrAddSerializer(serializers.Serializer):
    quality_profile_id = serializers.IntegerField(min_value=1)
    root_folder_path = serializers.CharField()
    minimum_availability = serializers.ChoiceField(choices=MINIMUM_AVAILABILITY_CHOICES)
    monitored = serializers.BooleanField()
    search_for_movie = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)


class RadarrRemoveSerializer(serializers.Serializer):
    delete_files = serializers.BooleanField()
    add_import_exclusion = serializers.BooleanField()
