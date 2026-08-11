from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from tracking.choices import ListPrivacy

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    followers_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()
    total_watched_movies = serializers.ReadOnlyField()
    total_watched_episodes = serializers.ReadOnlyField()
    preferred_region = serializers.CharField(max_length=2)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'bio', 'avatar', 'location',
            'website', 'preferred_region', 'is_private', 'followers_count', 'following_count',
            'total_watched_movies', 'total_watched_episodes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_preferred_region(self, value):
        region = (value or '').strip().upper()
        if len(region) != 2 or not region.isalpha():
            raise serializers.ValidationError('preferred_region must be a 2-letter country code.')
        return region


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class PublicUserSerializer(serializers.ModelSerializer):
    followers_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()
    total_watched_movies = serializers.ReadOnlyField()
    total_watched_episodes = serializers.ReadOnlyField()
    public_lists = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'bio', 'avatar', 'location',
            'followers_count', 'following_count',
            'total_watched_movies', 'total_watched_episodes', 'created_at',
            'public_lists'
        ]

    def get_public_lists(self, obj):
        from tracking.models import CustomList
        from tracking.serializers import CustomListSerializer
        lists = CustomList.objects.filter(user=obj, privacy=ListPrivacy.PUBLIC)
        return CustomListSerializer(lists, many=True).data


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        user = self.context['request'].user
        validate_password(value, user=user)
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
