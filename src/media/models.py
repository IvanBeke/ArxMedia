from django.db import models


class Genre(models.Model):
    tmdb_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Movie(models.Model):
    tmdb_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=500)
    overview = models.TextField(blank=True)
    poster_path = models.CharField(max_length=200, blank=True)
    backdrop_path = models.CharField(max_length=200, blank=True)
    release_date = models.DateField(null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True)
    vote_average = models.FloatField(default=0)
    vote_count = models.IntegerField(default=0)
    genres = models.ManyToManyField(Genre, blank=True)
    language = models.CharField(max_length=10, blank=True)
    tagline = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['release_date']),
        ]

    def __str__(self):
        return self.title

    @property
    def poster_url(self):
        if self.poster_path:
            return f'https://image.tmdb.org/t/p/w500{self.poster_path}'
        return None

    @property
    def backdrop_url(self):
        if self.backdrop_path:
            return f'https://image.tmdb.org/t/p/w1280{self.backdrop_path}'
        return None


class TVShow(models.Model):
    tmdb_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=500)
    overview = models.TextField(blank=True)
    poster_path = models.CharField(max_length=200, blank=True)
    backdrop_path = models.CharField(max_length=200, blank=True)
    first_air_date = models.DateField(null=True, blank=True)
    last_air_date = models.DateField(null=True, blank=True)
    number_of_seasons = models.IntegerField(default=0)
    number_of_episodes = models.IntegerField(default=0)
    vote_average = models.FloatField(default=0)
    vote_count = models.IntegerField(default=0)
    genres = models.ManyToManyField(Genre, blank=True)
    language = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=50, blank=True)
    networks = models.CharField(max_length=500, blank=True)
    episode_runtime = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def poster_url(self):
        if self.poster_path:
            return f'https://image.tmdb.org/t/p/w500{self.poster_path}'
        return None

    @property
    def backdrop_url(self):
        if self.backdrop_path:
            return f'https://image.tmdb.org/t/p/w1280{self.backdrop_path}'
        return None


class Season(models.Model):
    show = models.ForeignKey(TVShow, on_delete=models.CASCADE, related_name='seasons')
    tmdb_id = models.IntegerField()
    season_number = models.IntegerField()
    name = models.CharField(max_length=200)
    overview = models.TextField(blank=True)
    poster_path = models.CharField(max_length=200, blank=True)
    air_date = models.DateField(null=True, blank=True)
    episode_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('show', 'season_number')

    def __str__(self):
        return f'{self.show.name} - Season {self.season_number}'

    @property
    def poster_url(self):
        if self.poster_path:
            return f'https://image.tmdb.org/t/p/w500{self.poster_path}'
        return None


class Episode(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='episodes')
    tmdb_id = models.IntegerField()
    episode_number = models.IntegerField()
    name = models.CharField(max_length=300)
    overview = models.TextField(blank=True)
    still_path = models.CharField(max_length=200, blank=True)
    air_date = models.DateField(null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True)
    vote_average = models.FloatField(default=0)
    vote_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('season', 'episode_number')
        ordering = ['episode_number']
        indexes = [
            models.Index(fields=['air_date']),
        ]

    def __str__(self):
        return f'{self.season.show.name} S{self.season.season_number:02d}E{self.episode_number:02d} - {self.name}'

    @property
    def still_url(self):
        if self.still_path:
            return f'https://image.tmdb.org/t/p/w300{self.still_path}'
        return None


class EpisodeCredit(models.Model):
    episode = models.OneToOneField(Episode, on_delete=models.CASCADE, related_name='credits')
    cast = models.JSONField(default=list, blank=True)
    crew = models.JSONField(default=list, blank=True)
    guest_stars = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Credits for {self.episode}'
