from common.urls import url
from modules.auth import views


urls = (
    url("/sign-in/", views.SignInView, name="sign_in"),
    url("/sign-up/", views.SignUpView, name="sign_up"),
    url("/sign-out/", views.SignOutView, method="GET", name="sign_out"),
    url("/change-password/", views.ChangePasswordView, method="POST", name="change_password"),
    url("/change-password/", views.ChangePasswordView, method="GET", name="change_password"),
    url("/api/auth/invite/", views.InviteUserAPIView, method="POST", name="invite"),
    url("/api/auth/reset-password/", views.ResetPasswordAPIView, method="POST", name="reset_pwd"),
)
