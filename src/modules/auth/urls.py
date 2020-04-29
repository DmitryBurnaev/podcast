from common.urls import url
from modules.auth import views


urls = (
    url("/sign-in/", views.SignInView, name="sign_in"),
    url("/sign-up/", views.SignUpView, name="sign_up"),
    url("/sign-out/", views.SignOutView, method="GET", name="sign_out"),
    url("/api/auth/invite/", views.InviteUserView, method="POST", name="invite"),
)
