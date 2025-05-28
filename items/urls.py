from django.urls import path
from . import views

urlpatterns = [
    # Ana Sayfa
    path('', views.HomeView.as_view(), name='home'),
    
    # Kullanıcı Kaydı
    path('register/', views.register, name='register'),

    # Logout
     path('accounts/logout/', views.custom_logout, name='logout'),
    
    # Kayıp Eşya
    path('lost-items/', views.LostItemListView.as_view(), name='lost-items'),
    path('lost-items/<int:pk>/', views.LostItemDetailView.as_view(), name='lost-item-detail'),
    path('lost-items/new/', views.LostItemCreateView.as_view(), name='lost-item-create'),
    path('lost-items/<int:pk>/update/', views.LostItemUpdateView.as_view(), name='lost-item-update'),
    path('lost-items/<int:pk>/delete/', views.LostItemDeleteView.as_view(), name='lost-item-delete'),
    
    # Bulunan Eşya
    path('found-items/', views.FoundItemListView.as_view(), name='found-items'),
    path('found-items/<int:pk>/', views.FoundItemDetailView.as_view(), name='found-item-detail'),
    path('found-items/new/', views.FoundItemCreateView.as_view(), name='found-item-create'),
    path('found-items/<int:pk>/update/', views.FoundItemUpdateView.as_view(), name='found-item-update'),
    path('found-items/<int:pk>/delete/', views.FoundItemDeleteView.as_view(), name='found-item-delete'),

    # Çözümlenen İlanlar (Admin/Staff için)
    path('solved-items/', views.SolvedItemsListView.as_view(), name='solved-items'),
    
    # Talepler
    path('claims/', views.ClaimListView.as_view(), name='claims'),
    path('claims/<int:pk>/', views.ClaimDetailView.as_view(), name='claim-detail'),
    path('lost-items/<int:pk>/claim/', views.create_claim_for_lost_item, name='lost-item-claim'),
    path('found-items/<int:pk>/claim/', views.create_claim_for_found_item, name='found-item-claim'),
    path('claims/<int:pk>/update-status/', views.update_claim_status, name='claim-update-status'),
    path('claims/<int:pk>/delete/', views.ClaimDeleteView.as_view(), name='claim-delete'),
    path('claims/<int:pk>/approve/', views.approve_claim, name='approve-claim'),

    
    # Kategoriler
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/update/', views.CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),
    
    # Arama
    path('search/', views.search_view, name='search'),
    
    # İçeri/Dışarı Veri Aktarma
    path('import-export/', views.import_export_view, name='import-export'),

    #Mesajlaşma
    path('messages/', views.message_inbox, name='message-inbox'),
    path('messages/claim/<int:claim_id>/', views.view_conversation, name='view-conversation'),
    path('messages/claim/<int:claim_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('messages/claim/<int:claim_id>/delete-ajax/', views.delete_conversation_ajax, name='delete_conversation_ajax'),
]