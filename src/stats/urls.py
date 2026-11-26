from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register('', views.StatsViewSet, basename='stats')

urlpatterns = router.urls
