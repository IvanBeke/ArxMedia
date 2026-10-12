import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user-{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    account_visibility = "public"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs.setdefault("password", "testpass123")
        return model_class._default_manager.create_user(*args, **kwargs)
