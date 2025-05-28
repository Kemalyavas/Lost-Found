# items/admin.py
from django.contrib import admin
from .models import LostItem, FoundItem, Claim, ItemCategory, UserProfile, Message

@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'icon']
    search_fields = ['name']

@admin.register(LostItem)
class LostItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'lost_date', 'lost_location', 'status', 'reporter', 'created_at']
    list_filter = ['status', 'category', 'lost_date']
    search_fields = ['name', 'description', 'lost_location']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'lost_date'

@admin.register(FoundItem)
class FoundItemAdmin(admin.ModelAdmin):
    # found_location kaldırıldı
    list_display = ['name', 'category', 'found_date', 'status', 'finder', 'created_at']
    list_filter = ['status', 'category', 'found_date']
    search_fields = ['name', 'description']  # found_location kaldırıldı
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'found_date'

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ['get_item_name', 'claimed_by', 'status', 'claim_date']
    list_filter = ['status', 'claim_date']
    search_fields = ['claim_description', 'admin_notes']
    readonly_fields = ['claim_date']
    
    def get_item_name(self, obj):
        if obj.lost_item:
            return f"Kayıp: {obj.lost_item.name}"
        elif obj.found_item:
            return f"Bulunan: {obj.found_item.name}"
        return "Bilinmeyen"
    get_item_name.short_description = 'Eşya'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'user_type', 'phone', 'department']
    list_filter = ['user_type']
    search_fields = ['user__username', 'user__email', 'phone', 'department']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'claim', 'timestamp', 'is_read']
    list_filter = ['is_read', 'timestamp']
    search_fields = ['content', 'sender__username', 'receiver__username']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'