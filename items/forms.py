# items/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.models import User
from .models import LostItem, FoundItem, Claim, UserProfile, ItemCategory, Message
import csv
import io

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True) # E-postayı zorunlu yapalım
    first_name = forms.CharField(max_length=30, required=True, label='Ad')
    last_name = forms.CharField(max_length=150, required=True, label='Soyad') # max_length User modeli ile uyumlu olsun

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email'] # password1 ve password2 UserCreationForm'dan gelir

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label='E-posta Adresi')
    first_name = forms.CharField(max_length=30, required=False, label='Ad')
    last_name = forms.CharField(max_length=150, required=False, label='Soyad')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'department']
        widgets = { # Form alanlarına stil vermek için widget'ları kullanabiliriz
            'phone': forms.TextInput(attrs={'placeholder': 'örn: 5551234567'}),
            'department': forms.TextInput(attrs={'placeholder': 'örn: Bilgisayar Mühendisliği'}),
        }

class CustomPasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fieldname in ['old_password', 'new_password1', 'new_password2']:
            self.fields[fieldname].help_text = None
            # İsterseniz buraya CSS sınıfları ekleyebilirsiniz:
            # self.fields[fieldname].widget.attrs.update({'class': 'form-control-custom'})


class LostItemForm(forms.ModelForm):
    new_category = forms.CharField(required=False, label="Yeni Kategori (Listede yoksa)")

    class Meta:
        model = LostItem
        fields = ['name', 'description', 'category', 'lost_date', 'lost_location', 'contact_info', 'image']
        widgets = {
            'lost_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category_name = cleaned_data.get('new_category')

        if not category and not new_category_name:
            raise forms.ValidationError('Lütfen bir kategori seçin veya yeni bir kategori adı girin.')

        if new_category_name and category:
            raise forms.ValidationError("Lütfen ya var olan bir kategoriyi seçin ya da yeni bir kategori adı girin, ikisini birden değil.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_category_name = self.cleaned_data.get('new_category')

        if new_category_name and not self.cleaned_data.get('category'):
            # Yeni kategoriyi oluştur veya getir, büyük/küçük harf duyarsız kontrol et
            category, created = ItemCategory.objects.get_or_create(
                name__iexact=new_category_name,
                defaults={'name': new_category_name.strip(),
                          'description': f'{new_category_name.strip()} kategorisi (Otomatik Oluşturuldu)',
                          'icon': '🏷️'} # Varsayılan bir ikon
            )
            instance.category = category

        if commit:
            instance.save()
        return instance

class FoundItemForm(forms.ModelForm):
    new_category = forms.CharField(required=False, label="Yeni Kategori (Listede yoksa)")

    class Meta:
        model = FoundItem
        fields = ['name', 'description', 'category', 'found_date', 'image']
        widgets = {
            'found_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category_name = cleaned_data.get('new_category')

        if not category and not new_category_name:
            raise forms.ValidationError('Lütfen bir kategori seçin veya yeni bir kategori adı girin.')

        if new_category_name and category:
            raise forms.ValidationError("Lütfen ya var olan bir kategoriyi seçin ya da yeni bir kategori adı girin, ikisini birden değil.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_category_name = self.cleaned_data.get('new_category')

        if new_category_name and not self.cleaned_data.get('category'):
            category, created = ItemCategory.objects.get_or_create(
                name__iexact=new_category_name,
                defaults={'name': new_category_name.strip(),
                          'description': f'{new_category_name.strip()} kategorisi (Otomatik Oluşturuldu)',
                          'icon': '🏷️'}
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
                'class': 'chat-input' # Bu sınıf conversation.html'de stil için kullanılıyor
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'file-input', # Bu sınıf conversation.html'de stil için kullanılıyor
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.txt,.zip,.rar' # Desteklenen dosya tipleri
            })
        }

    def clean_content(self):
        content = self.cleaned_data.get('content')
        return content.strip() if content else content # Boşlukları temizle

    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        attachment = cleaned_data.get('attachment')

        if not content and not attachment:
            raise forms.ValidationError('Mesaj içeriği boş bırakılamaz veya bir dosya eklenmelidir.')
        return cleaned_data

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            if attachment.size > 10 * 1024 * 1024: # 10MB
                raise forms.ValidationError('Dosya boyutu 10MB\'dan büyük olamaz.')
            # Dosya tipi kontrolü (isteğe bağlı, modelde de yapılabilir)
            # Örneğin: allowed_extensions = ['.pdf', '.jpg']
        return attachment


class ClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ['claim_description']
        widgets = {
            'claim_description': forms.Textarea(attrs={'rows': 3}),
        }

class ClaimAdminForm(forms.ModelForm): # Bu admin paneli için, views.py'de kullanılıyor
    class Meta:
        model = Claim
        fields = ['status', 'admin_notes']
        widgets = {
            'admin_notes': forms.Textarea(attrs={'rows': 3}),
        }

class ItemCategoryForm(forms.ModelForm):
    class Meta:
        model = ItemCategory
        fields = ['name', 'description', 'icon']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class SearchForm(forms.Form):
    SEARCH_TYPES = [
        ('lost', 'Kayıp Eşyalar'),
        ('found', 'Bulunan Eşyalar'),
        ('all', 'Tümü'),
    ]

    search_term = forms.CharField(required=False, label='Arama Terimi', widget=forms.TextInput(attrs={'placeholder': 'Eşya adı, açıklama...'}))
    category = forms.ModelChoiceField(queryset=ItemCategory.objects.all(), required=False, label='Kategori', empty_label="Tüm Kategoriler")
    location = forms.CharField(required=False, label='Konum', widget=forms.TextInput(attrs={'placeholder': 'Kaybolduğu/bulunduğu yer...'}))
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

        if csv_file.size > 5 * 1024 * 1024: # 5MB
            raise forms.ValidationError('CSV dosyası 5MB\'dan büyük olamaz.')

        try:
            csv_file.seek(0)
            file_content = csv_file.read()
            decoded_content = ""
            encodings_to_try = ['utf-8-sig', 'utf-8', 'windows-1254', 'iso-8859-9']
            for enc in encodings_to_try:
                try:
                    decoded_content = file_content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if not decoded_content:
                raise forms.ValidationError(f"Dosya encoding formatı tanınamadı. Lütfen {', '.join(encodings_to_try)} formatlarından birini kullanın.")


            reader = csv.DictReader(io.StringIO(decoded_content))
            headers = reader.fieldnames

            if not headers:
                raise forms.ValidationError('CSV dosyası boş veya başlık satırı (header) içermiyor.')

            normalized_headers = [h.lower().strip().replace('ı', 'i').replace('ş', 's').replace('ğ', 'g').replace('ü', 'u').replace('ö', 'o').replace('ç', 'c') for h in headers if h]


            import_type = self.data.get('import_type') # cleaned_data henüz burada tam dolu olmayabilir.

            required_fields_map = {
                'lost': {
                    'name': ['ad', 'name', 'isim', 'esya adi'],
                    'description': ['aciklama', 'description', 'detay'],
                    'category': ['kategori', 'category'],
                    'date': ['tarih', 'lost_date', 'kayip tarihi'],
                    'location': ['yer', 'lost_location', 'location', 'konum', 'kayip yeri'],
                    'contact': ['iletisim', 'contact_info', 'contact', 'telefon', 'email']
                },
                'found': {
                    'name': ['ad', 'name', 'isim', 'esya adi'],
                    'description': ['aciklama', 'description', 'detay'],
                    'category': ['kategori', 'category'],
                    'date': ['tarih', 'found_date', 'bulunma tarihi']
                },
                'categories': {
                    'name': ['ad', 'name', 'isim', 'kategori adi'],
                    'description': ['aciklama', 'description', 'kategori aciklamasi']
                }
            }

            current_required_fields = required_fields_map.get(import_type, {})
            missing_fields = []

            for field_key, possible_headers in current_required_fields.items():
                if not any(ph in normalized_headers for ph in possible_headers):
                    missing_fields.append(field_key)

            if missing_fields:
                raise forms.ValidationError(
                    f"CSV dosyasında '{import_type}' tipi için şu zorunlu başlıklar eksik veya hatalı: {', '.join(missing_fields)}. "
                    f"Lütfen örnek CSV formatını kontrol edin. Kabul edilen başlıklar (küçük harf): "
                    f"{ {k: v for k, v in current_required_fields.items()} }"
                )

            csv_file.seek(0) # Dosya okuma imlecini başa al
        except forms.ValidationError:
            raise
        except Exception as e:
            raise forms.ValidationError(f"CSV dosyası okunamadı veya işlenemedi: {str(e)}")
        return csv_file
