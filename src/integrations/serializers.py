from rest_framework import serializers

MINIMUM_AVAILABILITY_CHOICES = ['announced', 'inCinemas', 'released']
SERIES_TYPE_CHOICES = ['standard', 'daily', 'anime']
MONITOR_CHOICES = ['all', 'future', 'missing', 'existing', 'recent', 'pilot', 'firstSeason', 'lastSeason', 'none']


class RadarrAddSerializer(serializers.Serializer):
    quality_profile_id = serializers.IntegerField(min_value=1)
    root_folder_path = serializers.CharField()
    minimum_availability = serializers.ChoiceField(choices=MINIMUM_AVAILABILITY_CHOICES)
    monitored = serializers.BooleanField()
    search_for_movie = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)


class SonarrAddSerializer(serializers.Serializer):
    quality_profile_id = serializers.IntegerField(min_value=1)
    root_folder_path = serializers.CharField()
    series_type = serializers.ChoiceField(choices=SERIES_TYPE_CHOICES)
    monitor = serializers.ChoiceField(choices=MONITOR_CHOICES)
    monitored = serializers.BooleanField()
    season_folder = serializers.BooleanField()
    search_for_missing_episodes = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)


class ArrRemoveSerializer(serializers.Serializer):
    delete_files = serializers.BooleanField()
    add_import_exclusion = serializers.BooleanField()
