from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.views import LogoutView, MeView, SignupView, UserDeleteView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='user-signup'),
    path('login/', TokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='user-me'),
    path('<uuid:user_id>/', UserDeleteView.as_view(), name='user-delete'),
]
