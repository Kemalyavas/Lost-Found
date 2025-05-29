# items/urls.py
from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Ana Sayfa
    path('', views.HomeView.as_view(), name='home'),

    # Kullanıcı Kaydı, Giriş, Çıkış
    path('kayit/', views.register, name='register'), # URL'i 'register/' yerine 'kayit/' olarak değiştirdim, daha Türkçe.
    path('giris/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'), # URL'i 'accounts/login/' yerine 'giris/'
    path('cikis/', views.custom_logout, name='logout'), # URL'i 'accounts/logout/' yerine 'cikis/'

    # Profil Sayfası
    path('profil/', views.profile_view, name='profile'), # URL'i 'accounts/profile/' yerine 'profil/'

    # Şifre Değiştirme URL'leri (Uygulama Arayüzü İçin)
    path('sifre-degistir/',
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change_form.html', # Kendi özel temanız
             success_url=reverse_lazy('password_change_done')
         ),
         name='password_change'),
    path('sifre-degistir/basarili/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='registration/password_change_done.html' # Kendi özel temanız
         ),
         name='password_change_done'),

    # Şifre Sıfırlama URL'leri (Uygulama Arayüzü İçin)
    path('sifre-sifirla/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt',
             success_url=reverse_lazy('password_reset_done')
         ),
         name='password_reset'),
    path('sifre-sifirla/gonderildi/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('sifre-sifirla-onayla/<uidb64>/<token>/', # URL daha anlaşılır hale getirildi
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url=reverse_lazy('password_reset_complete')
         ),
         name='password_reset_confirm'),
    path('sifre-sifirla/tamamlandi/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # Kayıp Eşya
    path('kayip-esyalar/', views.LostItemListView.as_view(), name='lost-items'),
    path('kayip-esyalar/<int:pk>/', views.LostItemDetailView.as_view(), name='lost-item-detail'),
    path('kayip-esyalar/yeni/', views.LostItemCreateView.as_view(), name='lost-item-create'),
    path('kayip-esyalar/<int:pk>/guncelle/', views.LostItemUpdateView.as_view(), name='lost-item-update'),
    path('kayip-esyalar/<int:pk>/sil/', views.LostItemDeleteView.as_view(), name='lost-item-delete'),

    # Bulunan Eşya
    path('bulunan-esyalar/', views.FoundItemListView.as_view(), name='found-items'),
    path('bulunan-esyalar/<int:pk>/', views.FoundItemDetailView.as_view(), name='found-item-detail'),
    path('bulunan-esyalar/yeni/', views.FoundItemCreateView.as_view(), name='found-item-create'),
    path('bulunan-esyalar/<int:pk>/guncelle/', views.FoundItemUpdateView.as_view(), name='found-item-update'),
    path('bulunan-esyalar/<int:pk>/sil/', views.FoundItemDeleteView.as_view(), name='found-item-delete'),

    # Çözümlenen İlanlar (Admin/Staff için)
    path('cozumlenen-ilanlar/', views.SolvedItemsListView.as_view(), name='solved-items'),
    path('cozumlenen-ilanlar/<str:item_type>/<int:pk>/', views.SolvedItemDetailView.as_view(), name='solved-item-detail'),

    # Talepler
    path('talepler/', views.ClaimListView.as_view(), name='claims'),
    path('talepler/<int:pk>/', views.ClaimDetailView.as_view(), name='claim-detail'),
    path('kayip-esyalar/<int:pk>/talep-et/', views.create_claim_for_lost_item, name='lost-item-claim'), # URL adı daha anlaşılır
    path('bulunan-esyalar/<int:pk>/talep-et/', views.create_claim_for_found_item, name='found-item-claim'), # URL adı daha anlaşılır
    path('talepler/<int:pk>/durum-guncelle/', views.update_claim_status, name='claim-update-status'),
    path('talepler/<int:pk>/sil/', views.ClaimDeleteView.as_view(), name='claim-delete'),
    path('talepler/<int:pk>/onayla/', views.approve_claim, name='approve-claim'),

    # Kategoriler
    path('kategoriler/', views.CategoryListView.as_view(), name='categories'),
    path('kategoriler/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    path('kategoriler/yeni/', views.CategoryCreateView.as_view(), name='category-create'),
    path('kategoriler/<int:pk>/guncelle/', views.CategoryUpdateView.as_view(), name='category-update'),
    path('kategoriler/<int:pk>/sil/', views.CategoryDeleteView.as_view(), name='category-delete'),

    # Arama
    path('arama/', views.search_view, name='search'),

    # İçeri/Dışarı Veri Aktarma
    path('veri-aktarimi/', views.import_export_view, name='import-export'),

    #Mesajlaşma
    path('mesajlar/', views.message_inbox, name='message-inbox'),
    path('mesajlar/talep/<int:claim_id>/', views.view_conversation, name='view-conversation'),
    path('mesajlar/talep/<int:claim_id>/sil/', views.delete_conversation, name='delete_conversation'),
    path('mesajlar/talep/<int:claim_id>/sil-ajax/', views.delete_conversation_ajax, name='delete_conversation_ajax'),
]
