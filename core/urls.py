from django.urls import path
from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("dashboard/estudante/", views.StudentDashboardView.as_view(), name="student_dashboard"),
    path("dashboard/empresa/", views.CompanyDashboardView.as_view(), name="company_dashboard"),
    path("dashboard/admin/", views.AdminDashboardView.as_view(), name="admin_dashboard"),
]
