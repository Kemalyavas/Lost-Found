import csv
import io
import json
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
from django.http import JsonResponse



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
    messages_list = Message.objects.filter(claim=claim).order_by('timestamp')
    
    # Okunmayan mesajları okundu olarak işaretleyin
    Message.objects.filter(claim=claim, receiver=request.user, is_read=False).update(is_read=True)
    
    # Yeni mesaj gönderme
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.receiver = other_user
            message.claim = claim
            
            # Eğer sadece dosya gönderiliyorsa içerik kısmını otomatik doldur
            if not message.content and message.attachment:
                message.content = f"📎 Dosya gönderildi: {message.attachment.name}"
            
            message.save()
            # Mesaj bildirimini kaldırdık - sadece redirect
            return redirect('view-conversation', claim_id=claim.id)
        else:
            # Sadece genel hata göster, detayları gösterme
            pass
    else:
        form = MessageForm()
    
    return render(request, 'items/messages/conversation.html', {
        'claim': claim,
        'other_user': other_user,
        'messages': messages_list,
        'form': form
    })

@login_required
def approve_claim(request, pk):
    """Eşya sahibinin talebi onaylaması"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Sadece POST isteği kabul edilir.'})
    
    claim = get_object_or_404(Claim, pk=pk)
    
    # Yetki kontrolü - sadece eşya sahibi onaylayabilir
    can_approve = False
    if claim.lost_item and request.user == claim.lost_item.reporter:
        can_approve = True
    elif claim.found_item and request.user == claim.found_item.finder:
        can_approve = True
    
    if not can_approve:
        return JsonResponse({'success': False, 'error': 'Bu talebi onaylama yetkiniz yok.'})
    
    # Talep zaten onaylanmış mı?
    if claim.status != 'pending':
        return JsonResponse({'success': False, 'error': 'Bu talep zaten işlem görmüş.'})
    
    try:
        from django.utils import timezone
        
        # Talebi onayla
        claim.status = 'approved'
        claim.admin_notes = f'Eşya sahibi tarafından onaylandı - {request.user.get_full_name() or request.user.username}'
        claim.save()
        
        # Eşyanın durumunu 'solved' yap (siteden kalkacak)
        if claim.lost_item:
            claim.lost_item.status = 'solved'
            claim.lost_item.solved_date = timezone.now()
            claim.lost_item.solved_by_claim = claim
            claim.lost_item.save()
        elif claim.found_item:
            claim.found_item.status = 'solved'
            claim.found_item.solved_date = timezone.now()
            claim.found_item.solved_by_claim = claim
            claim.found_item.save()
        
        # Otomatik sistem mesajı gönder
        system_message = Message.objects.create(
            sender=request.user,
            receiver=claim.claimed_by,
            claim=claim,
            content="🎉 Harika! Talebiniz onaylandı. Eşya sorunu çözüldü ve ilan siteden kaldırıldı."
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Talep başarıyla onaylandı! İlan siteden kaldırıldı.',
            'redirect_url': '/lost-items/'  # Ana sayfa veya liste sayfasına yönlendir
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

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

class SolvedItemsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin için çözümlenen ilanlar listesi"""
    template_name = 'items/admin/solved_items.html'
    context_object_name = 'solved_items'
    paginate_by = 20
    
    def test_func(self):
        return is_staff_or_admin(self.request.user)
    
    def get_queryset(self):
        # Hem kayıp hem bulunan eşyaları birleştir
        from django.db.models import Q
        lost_items = LostItem.objects.filter(status='solved').select_related('reporter', 'solved_by_claim', 'category')
        found_items = FoundItem.objects.filter(status='solved').select_related('finder', 'solved_by_claim', 'category')
        
        # Birleştirip tarihe göre sırala
        all_solved = []
        
        for item in lost_items:
            all_solved.append({
                'type': 'lost',
                'item': item,
                'item_name': item.name,
                'category': item.category,
                'solved_date': item.solved_date,
                'item_owner': item.reporter,  # Kaybeden
                'other_party': item.solved_by_claim.claimed_by if item.solved_by_claim else None,  # Bulan
                'claim': item.solved_by_claim,
                'location': item.lost_location,
                'date': item.lost_date,
            })
        
        for item in found_items:
            all_solved.append({
                'type': 'found',
                'item': item,
                'item_name': item.name,
                'category': item.category,
                'solved_date': item.solved_date,
                'item_owner': item.solved_by_claim.claimed_by if item.solved_by_claim else None,
                'other_party': item.finder, 
                'claim': item.solved_by_claim,
                'location': 'Gizli (Güvenlik)',
                'date': item.found_date,
            })
        
        # Tarihe göre sırala (en yeni önce)
        all_solved.sort(key=lambda x: x['solved_date'] if x['solved_date'] else x['item'].created_at, reverse=True)
        
        return all_solved
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # İstatistikler
        context['total_solved'] = LostItem.objects.filter(status='solved').count() + FoundItem.objects.filter(status='solved').count()
        context['solved_lost_items'] = LostItem.objects.filter(status='solved').count()
        context['solved_found_items'] = FoundItem.objects.filter(status='solved').count()
        
        return context

class SolvedItemDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Çözümlenen ilan detayı"""
    template_name = 'items/admin/solved_item_detail.html'
    context_object_name = 'solved_item'
    
    def test_func(self):
        return is_staff_or_admin(self.request.user)
    
    def get_object(self):
        item_type = self.kwargs.get('item_type')  # 'lost' veya 'found'
        item_id = self.kwargs.get('pk')
        
        if item_type == 'lost':
            item = get_object_or_404(LostItem, pk=item_id, status='solved')
            return {
                'type': 'lost',
                'item': item,
                'item_owner': item.reporter,
                'other_party': item.solved_by_claim.claimed_by if item.solved_by_claim else None,
                'claim': item.solved_by_claim,
            }
        elif item_type == 'found':
            item = get_object_or_404(FoundItem, pk=item_id, status='solved')
            return {
                'type': 'found',
                'item': item,
                'item_owner': item.solved_by_claim.claimed_by if item.solved_by_claim else None,
                'other_party': item.finder,
                'claim': item.solved_by_claim,
            }
        else:
            raise Http404()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Claim ile ilgili mesajları getir
        if context['solved_item']['claim']:
            context['messages'] = Message.objects.filter(
                claim=context['solved_item']['claim']
            ).order_by('timestamp')
        
        return context

# Ana Sayfa
class HomeView(TemplateView):
    template_name = 'items/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ana sayfada sadece aktif ilanları göster
        context['recent_lost_items'] = LostItem.objects.filter(status='lost').order_by('-created_at')[:5]
        context['recent_found_items'] = FoundItem.objects.filter(status='available').order_by('-created_at')[:5]
        
        if self.request.user.is_authenticated:
            # Kullanıcının TÜM ilanları (aktif + çözümlenmiş)
            context['user_lost_items'] = LostItem.objects.filter(
                reporter=self.request.user
            ).order_by('-created_at')[:3]
            
            context['user_found_items'] = FoundItem.objects.filter(
                finder=self.request.user
            ).order_by('-created_at')[:3]
            
            context['user_claims'] = Claim.objects.filter(
                claimed_by=self.request.user
            ).order_by('-claim_date')[:3]
        
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
        return LostItem.objects.filter(status='lost').order_by('-created_at')

class LostItemDetailView(DetailView):
    model = LostItem
    template_name = 'items/lost_items/detail.html'
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Kayıp eşya için: başkası "buldum, teslim etmek istiyorum" diyebilir
            context['can_claim'] = (self.object.status == 'lost' and 
                                   self.object.reporter != self.request.user)
            
            context['existing_claim'] = Claim.objects.filter(
                lost_item=self.object, 
                claimed_by=self.request.user
            ).first()
            
            # Button text'i değiştir
            context['claim_button_text'] = "Bu Eşyayı Buldum - Teslim Etmek İstiyorum"
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
       
        return FoundItem.objects.filter(status='available').order_by('-created_at')



class FoundItemDetailView(DetailView):
    model = FoundItem
    template_name = 'items/found_items/detail.html'
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Eğer kullanıcı giriş yapmışsa ve eşya kendisine ait DEĞİLSE talep etme özelliğini aktif et
        if self.request.user.is_authenticated:
            # Bulunan eşya için: gerçek sahibi "bu benim" diyebilir
            context['can_claim'] = (self.object.status == 'available' and 
                                   self.object.finder != self.request.user)
            
            context['existing_claim'] = Claim.objects.filter(
                found_item=self.object, 
                claimed_by=self.request.user
            ).first()
            
            # Button text'i değiştir
            context['claim_button_text'] = "Bu Benim Eşyam - Talep Ediyorum"
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
        user = self.request.user
        
        # Talep sahibi kontrolü
        if user == claim.claimed_by:
            return True
            
        # Eşya sahibi kontrolü (kayıp eşya)
        if claim.lost_item and user == claim.lost_item.reporter:
            return True
            
        # Eşya sahibi kontrolü (bulunan eşya)
        if claim.found_item and user == claim.found_item.finder:
            return True
            
        # Staff/admin kontrolü
        if is_staff_or_admin(user):
            return True
            
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_staff_or_admin'] = is_staff_or_admin(self.request.user)
        
        if context['is_staff_or_admin']:
            context['admin_form'] = ClaimAdminForm(instance=self.object)
            
        return context
    
@login_required
def create_claim_for_lost_item(request, pk):
    lost_item = get_object_or_404(LostItem, pk=pk)
    
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
            
            # Daha mantıklı otomatik mesaj
            reporter = lost_item.reporter
            initial_message = Message.objects.create(
                sender=request.user,
                receiver=reporter,
                claim=claim,
                content=f"Merhaba, '{lost_item.name}' adlı kayıp eşyanızı buldum ve size teslim etmek istiyorum. {claim.claim_description}"
            )
            
            messages.success(request, 'Teslim talebiniz başarıyla oluşturuldu. Eşya sahibiyle mesajlaşabilirsiniz.')
            return redirect('view-conversation', claim_id=claim.pk)
    else:
        form = ClaimForm()
        # Form placeholder'ını değiştir
        form.fields['claim_description'].widget.attrs['placeholder'] = 'Bu eşyayı nerede ve nasıl bulduğunuzu açıklayın...'
    
    return render(request, 'items/claims/create.html', {
        'form': form,
        'item': lost_item,
        'item_type': 'lost',
        'action_type': 'teslim'  # Template'de kullanmak için
    })

@login_required
def create_claim_for_found_item(request, pk):
    found_item = get_object_or_404(FoundItem, pk=pk)
    
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
            
            # Sahiplik iddiası mesajı
            finder = found_item.finder
            initial_message = Message.objects.create(
                sender=request.user,
                receiver=finder,
                claim=claim,
                content=f"Merhaba, '{found_item.name}' adlı bulduğunuz eşya benim. {claim.claim_description}"
            )
            
            messages.success(request, 'Sahiplik talebiniz başarıyla oluşturuldu. Eşyayı bulan kişiyle mesajlaşabilirsiniz.')
            return redirect('view-conversation', claim_id=claim.pk)
    else:
        form = ClaimForm()
        # Form placeholder'ını değiştir
        form.fields['claim_description'].widget.attrs['placeholder'] = 'Bu eşyanın size ait olduğunu nasıl kanıtlayabilirsiniz? (Renk, marka, içindeki öğeler, satın alma tarihi vb.)'
    
    return render(request, 'items/claims/create.html', {
        'form': form,
        'item': found_item,
        'item_type': 'found',
        'action_type': 'sahiplik'  # Template'de kullanmak için
    })


@login_required
def delete_conversation(request, claim_id):
    """Sohbeti silme fonksiyonu"""
    claim = get_object_or_404(Claim, pk=claim_id)
    
    # Yetki kontrolü - sadece ilgili taraflar silebilir
    can_delete = False
    if request.user == claim.claimed_by:
        can_delete = True
    elif claim.lost_item and request.user == claim.lost_item.reporter:
        can_delete = True
    elif claim.found_item and request.user == claim.found_item.finder:
        can_delete = True
    elif is_staff_or_admin(request.user):
        can_delete = True
    
    if not can_delete:
        raise PermissionDenied()
    
    if request.method == 'POST':
        # Sohbetteki tüm mesajları sil
        messages_count = Message.objects.filter(claim=claim).count()
        Message.objects.filter(claim=claim).delete()
        
        messages.success(
            request, 
            f'Sohbet başarıyla silindi. {messages_count} mesaj kalıcı olarak silindi.'
        )
        return redirect('message-inbox')
    
    # GET isteği - onay sayfası
    context = {
        'claim': claim,
        'messages_count': Message.objects.filter(claim=claim).count(),
    }
    
    # Karşı tarafın kim olduğunu belirle
    if request.user == claim.claimed_by:
        if claim.lost_item:
            context['other_user'] = claim.lost_item.reporter
        else:
            context['other_user'] = claim.found_item.finder
    else:
        context['other_user'] = claim.claimed_by
    
    return render(request, 'items/messages/delete_conversation.html', context)

@login_required
def delete_conversation_ajax(request, claim_id):
    """AJAX ile sohbet silme"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Sadece POST isteği kabul edilir.'})
    
    claim = get_object_or_404(Claim, pk=claim_id)
    
    # Yetki kontrolü
    can_delete = False
    if request.user == claim.claimed_by:
        can_delete = True
    elif claim.lost_item and request.user == claim.lost_item.reporter:
        can_delete = True
    elif claim.found_item and request.user == claim.found_item.finder:
        can_delete = True
    elif is_staff_or_admin(request.user):
        can_delete = True
    
    if not can_delete:
        return JsonResponse({'success': False, 'error': 'Bu sohbeti silme yetkiniz yok.'})
    
    try:
        # Mesaj sayısını al
        messages_count = Message.objects.filter(claim=claim).count()
        
        # Tüm mesajları sil
        Message.objects.filter(claim=claim).delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Sohbet başarıyla silindi. {messages_count} mesaj kalıcı olarak silindi.',
            'redirect_url': '/messages/'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

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
                    updated_claim.lost_item.status = 'claimed'  # 'solved' değil
                    updated_claim.lost_item.save()
                if updated_claim.found_item:
                    updated_claim.found_item.status = 'claimed'  # 'solved' değil
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
        user = self.request.user
        
        # Talep sahibi silebilir
        if user == claim.claimed_by:
            return True
            
        # Eşya sahibi silebilir (kayıp eşya)
        if claim.lost_item and user == claim.lost_item.reporter:
            return True
            
        # Eşya sahibi silebilir (bulunan eşya)
        if claim.found_item and user == claim.found_item.finder:
            return True
            
        # Staff/admin silebilir
        if is_staff_or_admin(user):
            return True
            
        return False
    
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
        # Kategoride sadece aktif ilanları göster
        context['lost_items'] = LostItem.objects.filter(
            category=self.object, 
            status='lost'  # Sadece kayıp durumundaki ilanlar
        ).order_by('-created_at')
        
        context['found_items'] = FoundItem.objects.filter(
            category=self.object, 
            status='available'  # Sadece mevcut durumundaki ilanlar
        ).order_by('-created_at')
        
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
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        search_type = form.cleaned_data.get('search_type')

        # Arama da sadece aktif ilanları göstersin
        if search_type in ['lost', 'all']:
            lost_items = LostItem.objects.filter(status='lost')  # Sadece aktif ilanlar

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

        if search_type in ['found', 'all']:
            found_items = FoundItem.objects.filter(status='available')  # Sadece aktif ilanlar

            query = Q()
            if search_term:
                query |= Q(name__icontains=search_term) | Q(description__icontains=search_term)
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
    if not is_staff_or_admin(request.user):
        raise PermissionDenied()
        
    import_form = CSVImportForm()
    
    if request.method == 'POST':
        # Export işlemleri
        if 'export_lost' in request.POST:
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="kayip_esyalar.csv"'
            response.write('\ufeff')  # UTF-8 BOM
            
            writer = csv.writer(response)
            writer.writerow(['Ad', 'Açıklama', 'Kategori', 'Tarih', 'Yer', 'İletişim', 'Durum', 'Bildiren'])
            
            lost_items = LostItem.objects.all().select_related('category', 'reporter')
            for item in lost_items:
                writer.writerow([
                    item.name,
                    item.description,
                    item.category.name,
                    item.lost_date.strftime('%d.%m.%Y'),
                    item.lost_location,
                    item.contact_info,
                    item.get_status_display(),
                    item.reporter.username
                ])
            return response
            
        elif 'export_found' in request.POST:
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="bulunan_esyalar.csv"'
            response.write('\ufeff')  # UTF-8 BOM
            
            writer = csv.writer(response)
            writer.writerow(['Ad', 'Açıklama', 'Kategori', 'Tarih', 'Durum', 'Bulan'])
            
            found_items = FoundItem.objects.all().select_related('category', 'finder')
            for item in found_items:
                writer.writerow([
                    item.name,
                    item.description,
                    item.category.name,
                    item.found_date.strftime('%d.%m.%Y'),
                    item.get_status_display(),
                    item.finder.username
                ])
            return response
            
        elif 'export_categories' in request.POST:
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="kategoriler.csv"'
            response.write('\ufeff')  # UTF-8 BOM
            
            writer = csv.writer(response)
            writer.writerow(['Ad', 'Açıklama', 'İkon'])
            
            for category in ItemCategory.objects.all():
                writer.writerow([
                    category.name, 
                    category.description,
                    category.icon if category.icon else ''
                ])
            return response
            
        # Import işlemleri
        elif 'import' in request.POST:
            import_form = CSVImportForm(request.POST, request.FILES)
            if import_form.is_valid():
                csv_file = request.FILES['csv_file']
                import_type = import_form.cleaned_data['import_type']
                
                # CSV dosyasını oku
                try:
                    # Farklı encoding'leri dene
                    csv_file.seek(0)
                    file_content = csv_file.read()
                    
                    # Önce UTF-8 BOM'lu dene
                    try:
                        decoded_content = file_content.decode('utf-8-sig')
                    except:
                        # UTF-8 dene
                        try:
                            decoded_content = file_content.decode('utf-8')
                        except:
                            # Windows-1254 (Türkçe) dene
                            try:
                                decoded_content = file_content.decode('windows-1254')
                            except:
                                # ISO-8859-9 (Türkçe) dene
                                decoded_content = file_content.decode('iso-8859-9')
                    
                    # CSV reader oluştur
                    csv_reader = csv.DictReader(io.StringIO(decoded_content))
                    
                    success_count = 0
                    error_count = 0
                    error_messages = []
                    
                    if import_type == 'lost':
                        for row_num, row in enumerate(csv_reader, start=2):  # 2'den başla (başlık satırı 1)
                            try:
                                # Kategori bul veya oluştur
                                category_name = row.get('Kategori') or row.get('kategori') or row.get('category')
                                if not category_name:
                                    raise ValueError("Kategori adı bulunamadı")
                                
                                category, created = ItemCategory.objects.get_or_create(
                                    name=category_name.strip(),
                                    defaults={
                                        'description': f'{category_name} kategorisi',
                                        'icon': '📦'
                                    }
                                )
                                
                                # Tarih formatını düzenle
                                date_str = row.get('Tarih') or row.get('tarih') or row.get('lost_date')
                                if not date_str:
                                    raise ValueError("Tarih bulunamadı")
                                
                                # Farklı tarih formatlarını dene
                                from datetime import datetime
                                date_formats = ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
                                lost_date = None
                                
                                for date_format in date_formats:
                                    try:
                                        lost_date = datetime.strptime(date_str.strip(), date_format).date()
                                        break
                                    except:
                                        continue
                                
                                if not lost_date:
                                    raise ValueError(f"Tarih formatı tanınamadı: {date_str}")
                                
                                # Kayıp eşya oluştur
                                LostItem.objects.create(
                                    name=(row.get('Ad') or row.get('ad') or row.get('name') or '').strip(),
                                    description=(row.get('Açıklama') or row.get('açıklama') or row.get('description') or '').strip(),
                                    category=category,
                                    lost_date=lost_date,
                                    lost_location=(row.get('Yer') or row.get('yer') or row.get('lost_location') or '').strip(),
                                    contact_info=(row.get('İletişim') or row.get('iletişim') or row.get('contact_info') or '').strip(),
                                    reporter=request.user,
                                    status='lost'
                                )
                                success_count += 1
                                
                            except Exception as e:
                                error_count += 1
                                error_messages.append(f"Satır {row_num}: {str(e)}")
                                
                    elif import_type == 'found':
                        for row_num, row in enumerate(csv_reader, start=2):
                            try:
                                # Kategori bul veya oluştur
                                category_name = row.get('Kategori') or row.get('kategori') or row.get('category')
                                if not category_name:
                                    raise ValueError("Kategori adı bulunamadı")
                                
                                category, created = ItemCategory.objects.get_or_create(
                                    name=category_name.strip(),
                                    defaults={
                                        'description': f'{category_name} kategorisi',
                                        'icon': '📦'
                                    }
                                )
                                
                                # Tarih formatını düzenle
                                date_str = row.get('Tarih') or row.get('tarih') or row.get('found_date')
                                if not date_str:
                                    raise ValueError("Tarih bulunamadı")
                                
                                # Farklı tarih formatlarını dene
                                from datetime import datetime
                                date_formats = ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
                                found_date = None
                                
                                for date_format in date_formats:
                                    try:
                                        found_date = datetime.strptime(date_str.strip(), date_format).date()
                                        break
                                    except:
                                        continue
                                
                                if not found_date:
                                    raise ValueError(f"Tarih formatı tanınamadı: {date_str}")
                                
                                # Bulunan eşya oluştur
                                FoundItem.objects.create(
                                    name=(row.get('Ad') or row.get('ad') or row.get('name') or '').strip(),
                                    description=(row.get('Açıklama') or row.get('açıklama') or row.get('description') or '').strip(),
                                    category=category,
                                    found_date=found_date,
                                    finder=request.user,
                                    status='available'
                                )
                                success_count += 1
                                
                            except Exception as e:
                                error_count += 1
                                error_messages.append(f"Satır {row_num}: {str(e)}")
                                
                    elif import_type == 'categories':
                        for row_num, row in enumerate(csv_reader, start=2):
                            try:
                                name = (row.get('Ad') or row.get('ad') or row.get('name') or '').strip()
                                if not name:
                                    raise ValueError("Kategori adı boş olamaz")
                                
                                # Kategori zaten var mı kontrol et
                                if ItemCategory.objects.filter(name=name).exists():
                                    error_messages.append(f"Satır {row_num}: '{name}' kategorisi zaten mevcut")
                                    error_count += 1
                                    continue
                                
                                ItemCategory.objects.create(
                                    name=name,
                                    description=(row.get('Açıklama') or row.get('açıklama') or row.get('description') or '').strip(),
                                    icon=(row.get('İkon') or row.get('ikon') or row.get('icon') or '📦').strip()
                                )
                                success_count += 1
                                
                            except Exception as e:
                                error_count += 1
                                error_messages.append(f"Satır {row_num}: {str(e)}")
                    
                    # Sonuç mesajlarını göster
                    if success_count > 0:
                        messages.success(request, f'{success_count} kayıt başarıyla içeri aktarıldı.')
                    
                    if error_count > 0:
                        error_detail = '<br>'.join(error_messages[:5])  # İlk 5 hatayı göster
                        if error_count > 5:
                            error_detail += f'<br>... ve {error_count - 5} hata daha'
                        messages.warning(request, f'{error_count} kayıt aktarılamadı:<br>{error_detail}', extra_tags='safe')
                        
                except Exception as e:
                    messages.error(request, f'CSV dosyası işlenirken hata oluştu: {str(e)}')
                    
                return redirect('import-export')
            else:
                # Form geçerli değilse hataları göster
                for field, errors in import_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
    
    return render(request, 'items/import_export.html', {
        'import_form': import_form
    })

def custom_logout(request):
    """
    Kullanıcıyı sistemden çıkartır ve ana sayfaya yönlendirir.
    """
    logout(request)
    return redirect('home')