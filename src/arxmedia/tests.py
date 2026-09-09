from accounts.models import User
from django.contrib import admin
from django.db import connection
from django.test import TestCase
from media.models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow
from social.models import Follow
from tracking.models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    Review,
    UserMediaStatus,
    WatchEntry,
)


class DatabaseSettingsTests(TestCase):
    def test_atomic_requests_enabled(self):
        self.assertIs(connection.settings_dict['ATOMIC_REQUESTS'], True)


class AdminConfigurationTests(TestCase):
    def test_all_models_are_registered(self):
        models = [
            User,
            Genre,
            Movie,
            TVShow,
            Season,
            Episode,
            EpisodeCredit,
            WatchEntry,
            Rating,
            Review,
            CustomList,
            ListItem,
            ListCollaborator,
            UserMediaStatus,
            DataTransferJob,
            Follow,
        ]

        for model in models:
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_admins_expose_core_changelist_configuration(self):
        models = [
            Movie,
            TVShow,
            Season,
            Episode,
            EpisodeCredit,
            WatchEntry,
            Rating,
            Review,
            CustomList,
            ListItem,
            ListCollaborator,
            UserMediaStatus,
            DataTransferJob,
            Follow,
        ]

        for model in models:
            model_admin = admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertTrue(model_admin.list_display)
                self.assertTrue(model_admin.search_fields)
                self.assertTrue(model_admin.list_filter)
                self.assertTrue(model_admin.ordering)
                self.assertTrue(model_admin.fieldsets)

        genre_admin = admin.site._registry[Genre]
        self.assertTrue(genre_admin.list_display)
        self.assertTrue(genre_admin.search_fields)
        self.assertTrue(genre_admin.ordering)
        self.assertTrue(genre_admin.fieldsets)

    def test_user_admin_includes_custom_profile_fields(self):
        user_admin = admin.site._registry[User]
        field_names = {
            field_name
            for _, options in user_admin.fieldsets
            for field_name in options['fields']
        }

        self.assertTrue({'bio', 'avatar', 'location', 'website', 'preferred_region', 'account_visibility'} <= field_names)
        self.assertIn('created_at', field_names)

    def test_requested_relationship_ordering(self):
        episode_ordering = ['season__show__name', 'season__season_number', 'episode_number']
        self.assertEqual(
            admin.site._registry[EpisodeCredit].ordering,
            ['episode__season__show__name', 'episode__season__season_number', 'episode__episode_number'],
        )
        self.assertEqual(admin.site._registry[Episode].ordering, episode_ordering)
        self.assertEqual(admin.site._registry[Season].ordering, ['show__name', 'season_number'])
        self.assertEqual(admin.site._registry[ListCollaborator].ordering, ['custom_list'])
        self.assertEqual(
            admin.site._registry[ListItem].ordering,
            ['custom_list__name', 'custom_order', 'added_at'],
        )

    def test_season_admin_displays_related_episode_count(self):
        show = TVShow.objects.create(tmdb_id=910001, name='Admin Count Check')
        season = Season.objects.create(
            show=show,
            tmdb_id=910002,
            season_number=1,
            name='Season 1',
        )
        episode = Episode.objects.create(
            season=season,
            tmdb_id=910003,
            episode_number=1,
            name='Episode 1',
        )

        season_admin = admin.site._registry[Season]
        self.assertEqual(season_admin.episode_count_display(season), 1)
        self.assertEqual(season.episode_count, 1)
        self.assertIsNone(season.air_date)

        episode.air_date = '2024-01-15'
        episode.save(update_fields=['air_date'])
        self.assertEqual(str(season.air_date), '2024-01-15')
