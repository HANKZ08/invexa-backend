from django.urls import path

from .views import ShopSettingsView

urlpatterns = [
    path("shop/settings/", ShopSettingsView.as_view(), name="shop_settings"),
]
