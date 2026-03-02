from django.urls import path

from users.views import SignupView, UserDeleteView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='user-signup'),
    path('<uuid:user_id>/', UserDeleteView.as_view(), name='user-delete'),
]
