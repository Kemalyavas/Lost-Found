from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

class ItemCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Kategori Adı")
    description = models.TextField(verbose_name="Kategori Açıklaması")
    icon = models.CharField(max_length=50, verbose_name="Kategori İkonu", blank=True)
    
    class Meta:
        verbose_name = "Eşya Kategorisi"
        verbose_name_plural = "Eşya Kategorileri"
    
    def __str__(self):
        return self.name

class LostItem(models.Model):
    STATUS_CHOICES = [
        ('lost', 'Kayıp'),
        ('claimed', 'Bulundu'),
        ('solved', 'Çözümlendi'), 
    ]
    
    name = models.CharField(max_length=100, verbose_name="Eşya Adı")
    description = models.TextField(verbose_name="Eşya Açıklaması")
    category = models.ForeignKey(ItemCategory, on_delete=models.CASCADE, verbose_name="Kategori")
    lost_date = models.DateField(verbose_name="Kaybolma Tarihi")
    lost_location = models.CharField(max_length=200, verbose_name="Kaybolduğu Yer")
    contact_info = models.CharField(max_length=100, verbose_name="İletişim Bilgisi")
    image = models.ImageField(upload_to='lost_items/', blank=True, null=True, verbose_name="Eşya Resmi")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='lost', verbose_name="Durum")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Bildiren Kişi")
    
    # Çözümlenen ilanlar için yeni alanlar
    solved_date = models.DateTimeField(null=True, blank=True, verbose_name="Çözümlenme Tarihi")
    solved_by_claim = models.ForeignKey('Claim', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Çözümleyen Talep")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    class Meta:
        verbose_name = "Kayıp Eşya"
        verbose_name_plural = "Kayıp Eşyalar"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    def get_absolute_url(self):
        return reverse('lost-item-detail', kwargs={'pk': self.pk})

class FoundItem(models.Model):
    STATUS_CHOICES = [
        ('available', 'Mevcut'),
        ('claimed', 'Sahip Bulundu'),
        ('solved', 'Çözümlendi'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Eşya Adı")
    description = models.TextField(verbose_name="Eşya Açıklaması")
    category = models.ForeignKey(ItemCategory, on_delete=models.CASCADE, verbose_name="Kategori")
    found_date = models.DateField(verbose_name="Bulunma Tarihi")
    # found_location field'ini kaldırdık - güvenlik için
    image = models.ImageField(upload_to='found_items/', blank=True, null=True, verbose_name="Eşya Resmi")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='available', verbose_name="Durum")
    finder = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Bulan Kişi")
    
    solved_date = models.DateTimeField(null=True, blank=True, verbose_name="Çözümlenme Tarihi")
    solved_by_claim = models.ForeignKey('Claim', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Çözümleyen Talep")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    class Meta:
        verbose_name = "Bulunan Eşya"
        verbose_name_plural = "Bulunan Eşyalar"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    def get_absolute_url(self):
        return reverse('found-item-detail', kwargs={'pk': self.pk})

class Claim(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Beklemede'),
        ('approved', 'Onaylandı'),
        ('rejected', 'Reddedildi'),
    ]
    
    lost_item = models.ForeignKey(LostItem, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Kayıp Eşya")
    found_item = models.ForeignKey(FoundItem, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Bulunan Eşya")
    claimed_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Talep Eden")
    claim_date = models.DateTimeField(auto_now_add=True, verbose_name="Talep Tarihi")
    claim_description = models.TextField(verbose_name="Talep Açıklaması")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="Durum")
    admin_notes = models.TextField(blank=True, verbose_name="Yönetici Notları")
    
    class Meta:
        verbose_name = "Talep"
        verbose_name_plural = "Talepler"
        ordering = ['-claim_date']
    
    def __str__(self):
        if self.lost_item:
            return f"Talep: {self.lost_item.name} - {self.get_status_display()}"
        elif self.found_item:
            return f"Talep: {self.found_item.name} - {self.get_status_display()}"
        else:
            return f"Talep: {self.pk} - {self.get_status_display()}"
    
    def get_absolute_url(self):
        return reverse('claim-detail', kwargs={'pk': self.pk})

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE, verbose_name="Gönderen")
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE, verbose_name="Alıcı")
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='messages', verbose_name="İlgili Talep")
    content = models.TextField(verbose_name="Mesaj İçeriği")
    attachment = models.FileField(upload_to='message_attachments/', blank=True, null=True, verbose_name="Dosya Eki")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Gönderim Zamanı") 
    is_read = models.BooleanField(default=False, verbose_name="Okundu mu")
    
    class Meta:
        verbose_name = "Mesaj"
        verbose_name_plural = "Mesajlar"
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.timestamp.strftime('%d.%m.%Y %H:%M')})"

# Kullanıcı grupları için profil modeli (Yetkilendirme için)
class UserProfile(models.Model):
    USER_TYPES = [
        ('regular', 'Normal Kullanıcı'),
        ('staff', 'Personel'),
        ('admin', 'Yönetici'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Kullanıcı")
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='regular', verbose_name="Kullanıcı Tipi")
    phone = models.CharField(max_length=15, blank=True, verbose_name="Telefon")
    department = models.CharField(max_length=100, blank=True, verbose_name="Bölüm/Departman")
    
    class Meta:
        verbose_name = "Kullanıcı Profili"
        verbose_name_plural = "Kullanıcı Profilleri"
    
    def __str__(self):
        return f"{self.user.username} - {self.get_user_type_display()}"