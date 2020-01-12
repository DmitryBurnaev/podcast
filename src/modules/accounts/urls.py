from common.urls import url
from modules.accounts import views


urls = (
    url("/sign-in/", views.SignInView, name="sign_in"),
    url("/sign-up/", views.SignUpView, name="sign_up"),
    url("/sign-out/", views.SignOutView, method="GET", name="sign_out"),
)
