from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import LostItem, FoundItem, Claim, UserProfile, ItemCategory, Message
import csv
import io

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=30, required=True, label='Ad')
    last_name = forms.CharField(max_length=30, required=True, label='Soyad')
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'department']

class LostItemForm(forms.ModelForm):
    new_category = forms.CharField(required=False, label="Yeni Kategori (Listede yoksa)")
    
    class Meta:
        model = LostItem
        fields = ['name', 'description', 'category', 'lost_date', 'lost_location', 'contact_info', 'image']
        widgets = {
            'lost_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category = cleaned_data.get('new_category')
        
        if not category and not new_category:
            raise forms.ValidationError('Lütfen bir kategori seçin veya yeni bir kategori girin.')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Eğer yeni kategori girilmişse, oluştur ve ata
        new_category = self.cleaned_data.get('new_category')
        if new_category and not self.cleaned_data.get('category'):
            category, created = ItemCategory.objects.get_or_create(
                name=new_category,
                defaults={'description': f'{new_category} kategorisi', 'icon': '📦'}
            )
            instance.category = category
        
        if commit:
            instance.save()
        
        return instance

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 1, 
                'placeholder': 'Mesajınızı yazın...',
                'class': 'chat-input'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'file-input',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.txt'
            })
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        return content
    
    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        attachment = cleaned_data.get('attachment')
        
        # İçerik veya dosya en az birisi olmalı
        if not content and not attachment:
            raise forms.ValidationError('Mesaj içeriği veya dosya eklemek zorunludur.')
        
        return cleaned_data
    
    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        
        if attachment:
            # Dosya boyutu kontrolü (10MB)
            if attachment.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Dosya boyutu 10MB\'dan küçük olmalıdır.')
            
            # Dosya tipi kontrolü
            allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt']
            file_extension = attachment.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise forms.ValidationError('Desteklenen dosya formatları: PDF, DOC, DOCX, JPG, JPEG, PNG, TXT')
        
        return attachment

class FoundItemForm(forms.ModelForm):
    new_category = forms.CharField(required=False, label="Yeni Kategori (Listede yoksa)")
    
    class Meta:
        model = FoundItem
        fields = ['name', 'description', 'category', 'found_date', 'image']  # found_location kaldırıldı
        widgets = {
            'found_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category = cleaned_data.get('new_category')
        
        if not category and not new_category:
            raise forms.ValidationError('Lütfen bir kategori seçin veya yeni bir kategori girin.')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Eğer yeni kategori girilmişse, oluştur ve ata
        new_category = self.cleaned_data.get('new_category')
        if new_category and not self.cleaned_data.get('category'):
            category, created = ItemCategory.objects.get_or_create(
                name=new_category,
                defaults={'description': f'{new_category} kategorisi', 'icon': '📦'}
            )
            instance.category = category
        
        if commit:
            instance.save()
        
        return instance

class ClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ['claim_description']

class ClaimAdminForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ['status', 'admin_notes']

class ItemCategoryForm(forms.ModelForm):
    class Meta:
        model = ItemCategory
        fields = ['name', 'description', 'icon']

class SearchForm(forms.Form):
    SEARCH_TYPES = [
        ('lost', 'Kayıp Eşyalar'),
        ('found', 'Bulunan Eşyalar'),
        ('all', 'Tümü'),
    ]
    
    search_term = forms.CharField(required=False, label='Arama Terimi')
    category = forms.ModelChoiceField(queryset=ItemCategory.objects.all(), required=False, label='Kategori')
    location = forms.CharField(required=False, label='Konum')
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='Başlangıç Tarihi')
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='Bitiş Tarihi')
    search_type = forms.ChoiceField(choices=SEARCH_TYPES, initial='all', label='Arama Tipi')

class CSVImportForm(forms.Form):
    IMPORT_TYPES = [
        ('lost', 'Kayıp Eşyalar'),
        ('found', 'Bulunan Eşyalar'),
        ('categories', 'Kategoriler'),
    ]
    
    csv_file = forms.FileField(label='CSV Dosyası')
    import_type = forms.ChoiceField(choices=IMPORT_TYPES, label='İçeri Aktarma Tipi')
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        if not csv_file.name.endswith('.csv'):
            raise forms.ValidationError('Dosya CSV formatında olmalıdır.')
        
        # Dosya boyutunu kontrol et (5MB max)
        if csv_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('CSV dosyası 5MB\'dan büyük olamaz.')
        
        # CSV formatını kontrol et
        try:
            csv_file.seek(0)
            # Farklı encoding'leri dene
            file_content = csv_file.read()
            
            # Encoding'i tespit et
            try:
                decoded_content = file_content.decode('utf-8-sig')
            except:
                try:
                    decoded_content = file_content.decode('utf-8')
                except:
                    try:
                        decoded_content = file_content.decode('windows-1254')
                    except:
                        decoded_content = file_content.decode('iso-8859-9')
            
            reader = csv.DictReader(io.StringIO(decoded_content))
            headers = reader.fieldnames
            
            if not headers:
                raise forms.ValidationError('CSV dosyası boş veya başlık satırı yok.')
            
            # Header'ları normalize et (küçük harf, boşlukları temizle)
            normalized_headers = [h.lower().strip() for h in headers]
            
            # İçeri aktarma tipine göre gerekli alanları kontrol et
            import_type = self.data.get('import_type')  # cleaned_data henüz hazır değil
            
            if import_type == 'lost':
                # Türkçe ve İngilizce başlıkları kabul et
                required_fields = {
                    'name': ['ad', 'name', 'isim'],
                    'description': ['açıklama', 'description', 'aciklama'],
                    'category': ['kategori', 'category'],
                    'date': ['tarih', 'lost_date', 'date'],
                    'location': ['yer', 'lost_location', 'location', 'konum'],
                    'contact': ['iletişim', 'contact_info', 'contact', 'iletisim']
                }
            elif import_type == 'found':
                required_fields = {
                    'name': ['ad', 'name', 'isim'],
                    'description': ['açıklama', 'description', 'aciklama'],
                    'category': ['kategori', 'category'],
                    'date': ['tarih', 'found_date', 'date']
                }
            elif import_type == 'categories':
                required_fields = {
                    'name': ['ad', 'name', 'isim'],
                    'description': ['açıklama', 'description', 'aciklama']
                }
            else:
                required_fields = {}
            
            # Her gerekli alan için en az bir başlık var mı kontrol et
            missing_fields = []
            for field_name, possible_headers in required_fields.items():
                found = False
                for header in possible_headers:
                    if header in normalized_headers:
                        found = True
                        break
                if not found:
                    missing_fields.append(field_name)
            
            if missing_fields:
                raise forms.ValidationError(
                    f"CSV dosyasında şu alanlar eksik: {', '.join(missing_fields)}. "
                    f"Lütfen örnek formatlara uygun bir CSV dosyası yükleyin."
                )
            
            # Dosya pozisyonunu başa al
            csv_file.seek(0)
                    
        except forms.ValidationError:
            raise
        except Exception as e:
            raise forms.ValidationError(f"CSV dosyası okunamadı: {str(e)}")
        
        return csv_file