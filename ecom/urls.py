from django.urls import path
from . import views

urlpatterns = [
    path('market-basket-analysis/', views.market_basket_analysis, name='market-basket-analysis'),
    path('view-transactions/', views.view_transactions, name='view-transactions'),
] 