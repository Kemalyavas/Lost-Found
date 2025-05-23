from django.contrib import admin
from .models import LostItem, FoundItem, Claim, ItemCategory, UserProfile, Message

class LostItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'lost_date', 'lost_location', 'status', 'reporter')
    list_filter = ('status', 'category', 'lost_date')
    search_fields = ('name', 'description', 'lost_location')
    date_hierarchy = 'lost_date'

class FoundItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'found_date', 'found_location', 'status', 'finder')
    list_filter = ('status', 'category', 'found_date')
    search_fields = ('name', 'description', 'found_location', 'current_location')
    date_hierarchy = 'found_date'

class ClaimAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'claimed_by', 'claim_date', 'status')
    list_filter = ('status', 'claim_date')
    search_fields = ('claimed_by__username', 'claim_description')
    date_hierarchy = 'claim_date'

class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'claim', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('sender__username', 'receiver__username', 'content')
    date_hierarchy = 'timestamp'

admin.site.register(Message, MessageAdmin)

class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'phone', 'department')
    list_filter = ('user_type',)
    search_fields = ('user__username', 'user__email', 'phone', 'department')

admin.site.register(LostItem, LostItemAdmin)
admin.site.register(FoundItem, FoundItemAdmin)
admin.site.register(Claim, ClaimAdmin)
admin.site.register(ItemCategory, ItemCategoryAdmin)
admin.site.register(UserProfile, UserProfileAdmin)