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
    
    path("deposito/solicitar/", views.SolicitarDepositoView.as_view(), name="solicitar_deposito"),
    path("deposito/checkout/<int:transacao_id>/", views.CheckoutDepositoView.as_view(), name="checkout_deposito"),
    path("deposito/confirmar-simulacao/<int:transacao_id>/", views.ConfirmarDepositoSimulacaoView.as_view(), name="confirmar_deposito_simulacao"),
    path("api/pagamentos/confirmar", views.ConfirmarDepositoWebhookView.as_view()),
    path("api/pagamentos/confirmar/", views.ConfirmarDepositoWebhookView.as_view(), name="api_confirmar_deposito"),
    
    path("api/vender/", views.RegistrarVendaView.as_view(), name="api_registrar_venda"),
    
    path("saque/solicitar/", views.SolicitarSaqueView.as_view(), name="solicitar_saque"),
    path("saque/aprovar/<int:saque_id>/", views.AprovarSaqueView.as_view(), name="aprovar_saque"),
    path("saque/recusar/<int:saque_id>/", views.RecusarSaqueView.as_view(), name="recusar_saque"),
    
    path("produto/criar/", views.CriarProdutoView.as_view(), name="criar_produto"),
    
    path("perfil/editar/", views.EditarPerfilView.as_view(), name="editar_perfil"),
]
