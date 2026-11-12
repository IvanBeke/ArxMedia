from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register('', views.NotificationViewSet, basename='notification')

urlpatterns = router.urls
