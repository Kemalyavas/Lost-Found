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
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mesajınızı buraya yazın...'}),
        }

class FoundItemForm(forms.ModelForm):
    class Meta:
        model = FoundItem
        fields = ['name', 'description', 'category', 'found_date', 'found_location', 'image']
        widgets = {
            'found_date': forms.DateInput(attrs={'type': 'date'}),
        }

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
        
        # CSV formatını kontrol et
        try:
            csv_file.seek(0)
            reader = csv.reader(io.StringIO(csv_file.read().decode('utf-8')))
            header = next(reader)
            # İçeri aktarma tipine göre başlıkları kontrol et
            import_type = self.cleaned_data.get('import_type')
            
            if import_type == 'lost':
                required_headers = ['name', 'description', 'category', 'lost_date', 'lost_location', 'contact_info']
            elif import_type == 'found':
                required_headers = ['name', 'description', 'category', 'found_date', 'found_location']
            elif import_type == 'categories':
                required_headers = ['name', 'description']
            
            for required_header in required_headers:
                if required_header not in header:
                    raise forms.ValidationError(f"CSV dosyasında '{required_header}' sütunu eksik.")
                    
        except Exception as e:
            raise forms.ValidationError(f"CSV dosyası okunamadı: {str(e)}")
        
        return csv_file