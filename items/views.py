import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.contrib.auth import logout
from django.shortcuts import redirect
from .forms import MessageForm

from .models import LostItem, FoundItem, Claim, ItemCategory, UserProfile, Message
from .forms import (LostItemForm, FoundItemForm, ClaimForm, ClaimAdminForm, 
                   UserRegisterForm, UserProfileForm, SearchForm, CSVImportForm,
                   ItemCategoryForm)

# Yardımcı fonksiyonlar
def is_staff_or_admin(user):
    if not user.is_authenticated:
        return False
    
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.user_type in ['staff', 'admin'] or user.is_staff or user.is_superuser
    except UserProfile.DoesNotExist:
        return user.is_staff or user.is_superuser

def is_admin(user):
    if not user.is_authenticated:
        return False
    
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.user_type == 'admin' or user.is_superuser
    except UserProfile.DoesNotExist:
        return user.is_superuser
    
@login_required
def view_conversation(request, claim_id):
    """Belirli bir talep için mesajlaşma sayfası"""
    claim = get_object_or_404(Claim, pk=claim_id)
    
    # Talep sahibi veya bildirimi yapan kişi değilse erişimi engelleyin
    if request.user != claim.claimed_by and (
        (claim.lost_item and request.user != claim.lost_item.reporter) or 
        (claim.found_item and request.user != claim.found_item.finder)
    ):
        raise PermissionDenied()
    
    # Karşı tarafın kim olduğunu belirleyin
    if request.user == claim.claimed_by:
        if claim.lost_item:
            other_user = claim.lost_item.reporter
        else:
            other_user = claim.found_item.finder
    else:
        other_user = claim.claimed_by
    
    # Mesajları getirin
    messages = Message.objects.filter(claim=claim).order_by('timestamp')
    
    # Okunmayan mesajları okundu olarak işaretleyin
    Message.objects.filter(claim=claim, receiver=request.user, is_read=False).update(is_read=True)
    
    # Yeni mesaj gönderme
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.receiver = other_user
            message.claim = claim
            message.save()
            return redirect('view-conversation', claim_id=claim.id)
    else:
        form = MessageForm()
    
    return render(request, 'items/messages/conversation.html', {
        'claim': claim,
        'other_user': other_user,
        'messages': messages,
        'form': form
    })

@login_required
def message_inbox(request):
    """Kullanıcının mesaj kutusu"""
    # Kullanıcının tüm talepleri
    user_claims = Claim.objects.filter(
        Q(claimed_by=request.user) | 
        Q(lost_item__reporter=request.user) | 
        Q(found_item__finder=request.user)
    ).distinct()
    
    # Her talep için son mesajı alın
    conversations = []
    for claim in user_claims:
        last_message = Message.objects.filter(claim=claim).order_by('-timestamp').first()
        
        if last_message:
            # Karşı tarafın kim olduğunu belirleyin
            if request.user == claim.claimed_by:
                if claim.lost_item:
                    other_user = claim.lost_item.reporter
                else:
                    other_user = claim.found_item.finder
            else:
                other_user = claim.claimed_by
            
            # Okunmamış mesaj sayısını hesaplayın
            unread_count = Message.objects.filter(
                claim=claim, receiver=request.user, is_read=False
            ).count()
            
            conversations.append({
                'claim': claim,
                'last_message': last_message,
                'other_user': other_user,
                'unread_count': unread_count
            })
    
    # Son mesaja göre sıralama
    conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else timezone.now(), reverse=True)
    
    return render(request, 'items/messages/inbox.html', {
        'conversations': conversations
    })

# Ana Sayfa
class HomeView(TemplateView):
    template_name = 'items/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_lost_items'] = LostItem.objects.filter(status='lost').order_by('-created_at')[:5]
        context['recent_found_items'] = FoundItem.objects.filter(status='available').order_by('-created_at')[:5]
        
        if self.request.user.is_authenticated:
            context['user_lost_items'] = LostItem.objects.filter(reporter=self.request.user).order_by('-created_at')[:3]
            context['user_found_items'] = FoundItem.objects.filter(finder=self.request.user).order_by('-created_at')[:3]
            context['user_claims'] = Claim.objects.filter(claimed_by=self.request.user).order_by('-claim_date')[:3]
        
        context['categories'] = ItemCategory.objects.all()
        return context

# Kullanıcı Kaydı
def register(request):
    if request.method == 'POST':
        u_form = UserRegisterForm(request.POST)
        p_form = UserProfileForm(request.POST)
        
        if u_form.is_valid() and p_form.is_valid():
            user = u_form.save()
            profile = p_form.save(commit=False)
            profile.user = user
            profile.save()
            
            # Kullanıcıyı otomatik giriş yap
            login(request, user)
            messages.success(request, 'Hesabınız başarıyla oluşturuldu!')
            return redirect('home')
    else:
        u_form = UserRegisterForm()
        p_form = UserProfileForm()
    
    return render(request, 'registration/register.html', {'u_form': u_form, 'p_form': p_form})



# Kayıp Eşya CRUD Views
class LostItemListView(ListView):
    model = LostItem
    template_name = 'items/lost_items/list.html'
    context_object_name = 'lost_items'
    paginate_by = 10
    
    def get_queryset(self):
        return LostItem.objects.order_by('-created_at')

class LostItemDetailView(DetailView):
    model = LostItem
    template_name = 'items/lost_items/detail.html'
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Eğer kullanıcı giriş yapmışsa ve eşya kendisine ait DEĞİLSE talep etme özelliğini aktif et
        if self.request.user.is_authenticated:
            # Kendi eşyasını talep edememesi için kontrol eklendi
            context['can_claim'] = (self.object.status == 'lost' and 
                                   self.object.reporter != self.request.user)
            
            context['existing_claim'] = Claim.objects.filter(
                lost_item=self.object, 
                claimed_by=self.request.user
            ).first()
        return context

class LostItemCreateView(LoginRequiredMixin, CreateView):
    model = LostItem
    form_class = LostItemForm
    template_name = 'items/lost_items/create.html'
    success_url = reverse_lazy('lost-items')
    
    def form_valid(self, form):
        form.instance.reporter = self.request.user
        messages.success(self.request, 'Kayıp eşya bildirimi başarıyla oluşturuldu.')
        return super().form_valid(form)

class LostItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = LostItem
    form_class = LostItemForm
    template_name = 'items/lost_items/update.html'
    
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.reporter or is_staff_or_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Kayıp eşya bildirimi başarıyla güncellendi.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('lost-item-detail', kwargs={'pk': self.object.pk})

class LostItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = LostItem
    template_name = 'items/lost_items/delete.html'
    success_url = reverse_lazy('lost-items')
    
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.reporter or is_staff_or_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Kayıp eşya bildirimi başarıyla silindi.')
        return super().delete(request, *args, **kwargs)

# Bulunan Eşya CRUD Views
class FoundItemListView(ListView):
    model = FoundItem
    template_name = 'items/found_items/list.html'
    context_object_name = 'found_items'
    paginate_by = 10
    
    def get_queryset(self):
        return FoundItem.objects.order_by('-created_at')

class FoundItemDetailView(DetailView):
    model = FoundItem
    template_name = 'items/found_items/detail.html'
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Eğer kullanıcı giriş yapmışsa ve eşya kendisine ait DEĞİLSE talep etme özelliğini aktif et
        if self.request.user.is_authenticated:
            context['can_claim'] = (self.object.status == 'available' and 
                                   self.object.finder != self.request.user)
            
            context['existing_claim'] = Claim.objects.filter(
                found_item=self.object, 
                claimed_by=self.request.user
            ).first()
        return context

class FoundItemCreateView(LoginRequiredMixin, CreateView):
    model = FoundItem
    form_class = FoundItemForm
    template_name = 'items/found_items/create.html'
    success_url = reverse_lazy('found-items')
    
    def form_valid(self, form):
        form.instance.finder = self.request.user
        messages.success(self.request, 'Bulunan eşya bildirimi başarıyla oluşturuldu.')
        return super().form_valid(form)

class FoundItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = FoundItem
    form_class = FoundItemForm
    template_name = 'items/found_items/update.html'
    
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.finder or is_staff_or_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Bulunan eşya bildirimi başarıyla güncellendi.')
        return super().form_valid(form)
    def get_success_url(self):
        return reverse_lazy('found-item-detail', kwargs={'pk': self.object.pk})

class FoundItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = FoundItem
    template_name = 'items/found_items/delete.html'
    success_url = reverse_lazy('found-items')
    
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.finder or is_staff_or_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Bulunan eşya bildirimi başarıyla silindi.')
        return super().delete(request, *args, **kwargs)
    

# Talep (Claim) CRUD Views
class ClaimListView(LoginRequiredMixin, ListView):
    model = Claim
    template_name = 'items/claims/list.html'
    context_object_name = 'claims'
    paginate_by = 10
    
    def get_queryset(self):
        if is_staff_or_admin(self.request.user):
            return Claim.objects.order_by('-claim_date')
        else:
            return Claim.objects.filter(claimed_by=self.request.user).order_by('-claim_date')

class ClaimDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Claim
    template_name = 'items/claims/detail.html'
    context_object_name = 'claim'
    
    def test_func(self):
        claim = self.get_object()
        return self.request.user == claim.claimed_by or is_staff_or_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_staff_or_admin'] = is_staff_or_admin(self.request.user)
        
        if context['is_staff_or_admin']:
            context['admin_form'] = ClaimAdminForm(instance=self.object)
            
        return context

@login_required
def create_claim_for_lost_item(request, pk):
    lost_item = get_object_or_404(LostItem, pk=pk)
    
    # Zaten talep var mı kontrol et
    existing_claim = Claim.objects.filter(lost_item=lost_item, claimed_by=request.user).first()
    if existing_claim:
        messages.warning(request, 'Bu eşya için zaten bir talebiniz bulunmaktadır.')
        return redirect('lost-item-detail', pk=pk)
    
    if request.method == 'POST':
        form = ClaimForm(request.POST)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.lost_item = lost_item
            claim.claimed_by = request.user
            claim.save()
            
            # Otomatik bir mesaj oluştur
            reporter = lost_item.reporter
            initial_message = Message.objects.create(
                sender=request.user,
                receiver=reporter,
                claim=claim,
                content=f"Merhaba, {lost_item.name} adlı kayıp eşyanız için bir talebim var. {claim.claim_description}"
            )
            
            messages.success(request, 'Talebiniz başarıyla oluşturuldu. Eşya sahibiyle mesajlaşabilirsiniz.')
            return redirect('view-conversation', claim_id=claim.pk)
    else:
        form = ClaimForm()
    
    return render(request, 'items/claims/create.html', {
        'form': form,
        'item': lost_item,
        'item_type': 'lost'
    })

@login_required
def create_claim_for_found_item(request, pk):
    found_item = get_object_or_404(FoundItem, pk=pk)
    
    # Zaten talep var mı kontrol et
    existing_claim = Claim.objects.filter(found_item=found_item, claimed_by=request.user).first()
    if existing_claim:
        messages.warning(request, 'Bu eşya için zaten bir talebiniz bulunmaktadır.')
        return redirect('found-item-detail', pk=pk)
    
    if request.method == 'POST':
        form = ClaimForm(request.POST)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.found_item = found_item
            claim.claimed_by = request.user
            claim.save()
            
            # Otomatik bir mesaj oluştur
            finder = found_item.finder
            initial_message = Message.objects.create(
                sender=request.user,
                receiver=finder,
                claim=claim,
                content=f"Merhaba, {found_item.name} adlı bulduğunuz eşya için bir talebim var. {claim.claim_description}"
            )
            
            messages.success(request, 'Talebiniz başarıyla oluşturuldu. Eşyayı bulan kişiyle mesajlaşabilirsiniz.')
            return redirect('view-conversation', claim_id=claim.pk)
    else:
        form = ClaimForm()
    
    return render(request, 'items/claims/create.html', {
        'form': form,
        'item': found_item,
        'item_type': 'found'
    })

@login_required
def update_claim_status(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    
    # Yalnızca personel ve yöneticiler talep durumunu güncelleyebilir
    if not is_staff_or_admin(request.user):
        raise PermissionDenied()
    
    if request.method == 'POST':
        form = ClaimAdminForm(request.POST, instance=claim)
        if form.is_valid():
            updated_claim = form.save()
            
            # Eğer talep onaylanmışsa, eşyanın durumunu güncelle
            if updated_claim.status == 'approved':
                if updated_claim.lost_item:
                    updated_claim.lost_item.status = 'claimed'
                    updated_claim.lost_item.save()
                if updated_claim.found_item:
                    updated_claim.found_item.status = 'claimed'
                    updated_claim.found_item.save()
            
            messages.success(request, 'Talep durumu başarıyla güncellendi.')
            return redirect('claim-detail', pk=claim.pk)
    else:
        form = ClaimAdminForm(instance=claim)
    
    return render(request, 'items/claims/update_status.html', {
        'form': form,
        'claim': claim
    })

class ClaimDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Claim
    template_name = 'items/claims/delete.html'
    success_url = reverse_lazy('claims')
    
    def test_func(self):
        claim = self.get_object()
        # Yalnızca talebi oluşturan kullanıcı veya personel/yöneticiler talebi silebilir
        return self.request.user == claim.claimed_by or is_staff_or_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Talep başarıyla silindi.')
        return super().delete(request, *args, **kwargs)

# Kategori CRUD Views
class CategoryListView(ListView):
    model = ItemCategory
    template_name = 'items/categories/list.html'
    context_object_name = 'categories'

class CategoryDetailView(DetailView):
    model = ItemCategory
    template_name = 'items/categories/detail.html'
    context_object_name = 'category'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lost_items'] = LostItem.objects.filter(category=self.object).order_by('-created_at')
        context['found_items'] = FoundItem.objects.filter(category=self.object).order_by('-created_at')
        return context

class CategoryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ItemCategory
    form_class = ItemCategoryForm
    template_name = 'items/categories/create.html'
    success_url = reverse_lazy('categories')
    
    def test_func(self):
        return is_staff_or_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Kategori başarıyla oluşturuldu.')
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ItemCategory
    form_class = ItemCategoryForm
    template_name = 'items/categories/update.html'
    success_url = reverse_lazy('categories')
    
    def test_func(self):
        return is_staff_or_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Kategori başarıyla güncellendi.')
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ItemCategory
    template_name = 'items/categories/delete.html'
    success_url = reverse_lazy('categories')
    
    def test_func(self):
        return is_staff_or_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Kategori başarıyla silindi.')
        return super().delete(request, *args, **kwargs)
    # Arama İşlemleri
def search_view(request):
    form = SearchForm(request.GET or None)
    lost_items = None
    found_items = None

    if form.is_valid() and any([form.cleaned_data.get(field) for field in form.cleaned_data]):
        search_term = form.cleaned_data.get('search_term')
        if search_term:
            search_term = search_term.strip()

        category = form.cleaned_data.get('category')

        location = form.cleaned_data.get('location')
        if location:
            location = location.strip()
        search_term = form.cleaned_data.get('search_term')
        category = form.cleaned_data.get('category')
        location = form.cleaned_data.get('location')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        search_type = form.cleaned_data.get('search_type')

        # Kayıp eşyaları filtrele
        if search_type in ['lost', 'all']:
            lost_items = LostItem.objects.all()

            # Arama kelimesi ve konum birlikte esnek arama
            query = Q()
            if search_term:
                query |= Q(name__icontains=search_term) | Q(description__icontains=search_term)
            if location:
                query |= Q(lost_location__icontains=location)
            if query:
                lost_items = lost_items.filter(query)

            if category and category != '--------':
                lost_items = lost_items.filter(category=category)
            if date_from:
                lost_items = lost_items.filter(lost_date__gte=date_from)
            if date_to:
                lost_items = lost_items.filter(lost_date__lte=date_to)

        # Bulunan eşyaları filtrele
        if search_type in ['found', 'all']:
            found_items = FoundItem.objects.all()

            # Arama kelimesi ve konum birlikte esnek arama
            query = Q()
            if search_term:
                query |= Q(name__icontains=search_term) | Q(description__icontains=search_term)
            if location:
                query |= Q(found_location__icontains=location) | Q(current_location__icontains=location)
            if query:
                found_items = found_items.filter(query)

            if category and category != '--------':
                found_items = found_items.filter(category=category)
            if date_from:
                found_items = found_items.filter(found_date__gte=date_from)
            if date_to:
                found_items = found_items.filter(found_date__lte=date_to)

    return render(request, 'items/search.html', {
        'form': form,
        'lost_items': lost_items,
        'found_items': found_items,
        'search_performed': form.is_valid() and any([form.cleaned_data.get(field) for field in form.cleaned_data])
    })


@login_required
def import_export_view(request):
    import_form = CSVImportForm()  # Bu satırı fonksiyonun başına taşıyın
    
    if request.method == 'POST':
        if 'import' in request.POST:
            import_form = CSVImportForm(request.POST, request.FILES)
            if import_form.is_valid():
                csv_file = import_form.cleaned_data['csv_file']
                import_type = import_form.cleaned_data['import_type']
                
                # CSV içeriğini oku
                csv_file.seek(0)
                reader = csv.DictReader(io.StringIO(csv_file.read().decode('utf-8')))
                
                if import_type == 'lost':
                    for row in reader:
                        # Kategoriyi bul veya oluştur
                        category, _ = ItemCategory.objects.get_or_create(name=row['category'])
                        
                        # Kayıp eşya oluştur
                        LostItem.objects.create(
                            name=row['name'],
                            description=row['description'],
                            category=category,
                            lost_date=row['lost_date'],
                            lost_location=row['lost_location'],
                            contact_info=row['contact_info'],
                            reporter=request.user,
                            status='lost'
                        )
                
                elif import_type == 'found':
                    for row in reader:
                        # Kategoriyi bul veya oluştur
                        category, _ = ItemCategory.objects.get_or_create(name=row['category'])
                        
                        # Bulunan eşya oluştur
                        FoundItem.objects.create(
                            name=row['name'],
                            description=row['description'],
                            category=category,
                            found_date=row['found_date'],
                            found_location=row['found_location'],
                            current_location="",
                            finder=request.user,
                            status='available'
                        )
                
                elif import_type == 'categories':
                    for row in reader:
                        # Kategori oluştur
                        ItemCategory.objects.get_or_create(
                            name=row['name'],
                            defaults={'description': row['description']}
                        )
                
                messages.success(request, 'Veriler başarıyla içeri aktarıldı.')
                return redirect('import-export')
        
        elif 'export_lost' in request.POST:
            # Kayıp eşyaları dışarı aktar
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="lost_items.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['name', 'description', 'category', 'lost_date', 'lost_location', 'contact_info', 'status'])
            
            lost_items = LostItem.objects.all()
            for item in lost_items:
                writer.writerow([
                    item.name,
                    item.description,
                    item.category.name,
                    item.lost_date,
                    item.lost_location,
                    item.contact_info,
                    item.get_status_display()
                ])
            
            return response
        
        elif 'export_found' in request.POST:
            # Bulunan eşyaları dışarı aktar
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="found_items.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['name', 'description', 'category', 'found_date', 'found_location', 'status'])
            
            found_items = FoundItem.objects.all()
            for item in found_items:
                writer.writerow([
                    item.name,
                    item.description,
                    item.category.name,
                    item.found_date,
                    item.found_location,
                    item.get_status_display()
                ])
            
            return response
        
        elif 'export_categories' in request.POST:
            # Kategorileri dışarı aktar
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="categories.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['name', 'description'])
            
            categories = ItemCategory.objects.all()
            for category in categories:
                writer.writerow([
                    category.name,
                    category.description
                ])
            
            return response
    
    return render(request, 'items/import_export.html', {
        'import_form': import_form
    })

def custom_logout(request):
    """
    Kullanıcıyı sistemden çıkartır ve ana sayfaya yönlendirir.
    """
    logout(request)
    return redirect('home')