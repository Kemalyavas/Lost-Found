# items/views.py
import csv
import io
import json # Bu import muhtemelen kullanılmıyor, kaldırılabilir.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import HttpResponse, JsonResponse # JsonResponse ekledik
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.contrib.auth import login, logout # logout ekledik
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist # ObjectDoesNotExist ekledik
# from django.shortcuts import redirect # Zaten var
from .forms import (
    MessageForm, LostItemForm, FoundItemForm, ClaimForm, ClaimAdminForm,
    UserRegisterForm, UserProfileForm, SearchForm, CSVImportForm,
    ItemCategoryForm, UserUpdateForm # UserUpdateForm'u import ettik
)
from .models import LostItem, FoundItem, Claim, ItemCategory, UserProfile, Message
from datetime import datetime # CSV import için


# Yardımcı fonksiyonlar
def is_staff_or_admin(user):
    if not user.is_authenticated:
        return False
    try:
        # UserProfile üzerinden kontrol et, yoksa is_staff veya is_superuser'a bak
        profile = user.userprofile # UserProfile.objects.get(user=user) yerine doğrudan erişim
        return profile.user_type in ['staff', 'admin']
    except UserProfile.DoesNotExist: # Profilin henüz oluşturulmadığı durumlar için
        return user.is_staff or user.is_superuser
    except AttributeError: # user.userprofile yoksa (çok eski kullanıcılar için nadir bir durum)
        return user.is_staff or user.is_superuser


def is_admin(user):
    if not user.is_authenticated:
        return False
    try:
        profile = user.userprofile
        return profile.user_type == 'admin'
    except UserProfile.DoesNotExist:
        return user.is_superuser
    except AttributeError:
        return user.is_superuser

# Kullanıcı Profili Görüntüleme ve Güncelleme
@login_required
def profile_view(request):
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        # Eğer kullanıcı için UserProfile nesnesi yoksa (örneğin admin paneli üzerinden oluşturulmuş kullanıcı)
        # varsayılan bir tane oluşturulabilir.
        user_profile = UserProfile.objects.create(user=request.user)
    except AttributeError: # request.user.userprofile yoksa
        messages.error(request, "Profil bilgilerinize erişirken bir sorun oluştu. Lütfen yönetici ile iletişime geçin.")
        return redirect('home')


    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = UserProfileForm(request.POST, instance=user_profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Profiliniz başarıyla güncellendi!')
            return redirect('profile')
        else:
            # Form hatalarını birleştirerek göster
            error_list = []
            for field, errors in u_form.errors.items():
                for error in errors:
                    error_list.append(f"{u_form.fields[field].label or field}: {error}")
            for field, errors in p_form.errors.items():
                for error in errors:
                    error_list.append(f"{p_form.fields[field].label or field}: {error}")
            if error_list:
                 messages.error(request, f"Lütfen formdaki hataları düzeltin: {'; '.join(error_list)}")
            else:
                messages.error(request, 'Profil güncellenirken bir hata oluştu. Lütfen formdaki hataları düzeltin.')

    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = UserProfileForm(instance=user_profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'user_profile': user_profile, # Template'de kullanıcı tipini vs. göstermek için
        'page_title': 'Profilim' # Dinamik başlık için
    }
    return render(request, 'registration/profile.html', context)


@login_required
def view_conversation(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)

    # Yetki kontrolü: Talep sahibi, eşyayı kaybeden, eşyayı bulan veya admin/staff olmalı
    is_related_user = (
        request.user == claim.claimed_by or
        (claim.lost_item and request.user == claim.lost_item.reporter) or
        (claim.found_item and request.user == claim.found_item.finder)
    )
    if not (is_related_user or is_staff_or_admin(request.user)):
        raise PermissionDenied("Bu konuşmayı görüntüleme yetkiniz yok.")

    if request.user == claim.claimed_by:
        other_user = claim.lost_item.reporter if claim.lost_item else claim.found_item.finder
    elif claim.lost_item and request.user == claim.lost_item.reporter:
        other_user = claim.claimed_by
    elif claim.found_item and request.user == claim.found_item.finder:
        other_user = claim.claimed_by
    else: # Admin/staff durumu için bir karşı taraf belirle (opsiyonel, duruma göre değişir)
        other_user = claim.claimed_by # Varsayılan olarak talep edeni gösterelim

    messages_list = Message.objects.filter(claim=claim).order_by('timestamp')
    Message.objects.filter(claim=claim, receiver=request.user, is_read=False).update(is_read=True)

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.receiver = other_user
            message.claim = claim
            if not message.content and message.attachment: # Sadece dosya gönderiliyorsa
                message.content = f"📎 Dosya: {message.attachment.name}"
            message.save()
            return redirect('view-conversation', claim_id=claim.id)
        else:
            # Form hatalarını kullanıcıya göster
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label if field != '__all__' else ''}: {error}")
    else:
        form = MessageForm()

    return render(request, 'items/messages/conversation.html', {
        'claim': claim,
        'other_user': other_user,
        'messages': messages_list,
        'form': form,
        'page_title': f"Mesaj: {other_user.get_full_name(fallback_username=True) if hasattr(other_user, 'get_full_name') else other_user.username}"
    })

@login_required
def approve_claim(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Sadece POST isteği kabul edilir.'}, status=405)

    claim = get_object_or_404(Claim, pk=pk)
    can_approve = False
    if claim.lost_item and request.user == claim.lost_item.reporter:
        can_approve = True
    elif claim.found_item and request.user == claim.found_item.finder:
        can_approve = True

    if not can_approve:
        return JsonResponse({'success': False, 'error': 'Bu talebi onaylama yetkiniz yok.'}, status=403)

    if claim.status != 'pending':
        return JsonResponse({'success': False, 'error': 'Bu talep zaten işlem görmüş.'}, status=400)

    try:
        claim.status = 'approved'
        claim.admin_notes = f'Eşya sahibi tarafından onaylandı - {request.user.get_full_name(fallback_username=True) if hasattr(request.user, "get_full_name") else request.user.username} ({timezone.now().strftime("%d.%m.%Y %H:%M")})'
        claim.save()

        item_to_solve = claim.lost_item or claim.found_item
        if item_to_solve:
            item_to_solve.status = 'solved' # Hem LostItem hem FoundItem için 'solved'
            item_to_solve.solved_date = timezone.now()
            item_to_solve.solved_by_claim = claim
            item_to_solve.save()
        
        # Otomatik sistem mesajı
        Message.objects.create(
            sender=request.user, # Onaylayan kişi (eşya sahibi)
            receiver=claim.claimed_by, # Talep eden kişi
            claim=claim,
            content="🎉 Harika! Talebiniz eşya sahibi tarafından onaylandı. Eşya sorunu çözüldü ve ilgili ilan siteden kaldırıldı."
        )

        messages.success(request, 'Talep başarıyla onaylandı! İlan siteden kaldırıldı.') # Redirect sonrası mesaj
        return JsonResponse({
            'success': True,
            'message': 'Talep başarıyla onaylandı! İlan siteden kaldırıldı.',
            'redirect_url': reverse('lost-items') # veya 'home'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Bir hata oluştu: {str(e)}'}, status=500)


@login_required
def message_inbox(request):
    user_claims = Claim.objects.filter(
        Q(claimed_by=request.user) |
        Q(lost_item__reporter=request.user) |
        Q(found_item__finder=request.user)
    ).distinct().select_related(
        'lost_item__reporter', 'found_item__finder', 'claimed_by'
    )

    conversations = []
    for claim in user_claims:
        last_message = Message.objects.filter(claim=claim).order_by('-timestamp').first()
        if last_message: # Sadece mesajı olan talepleri göster
            other_user = None
            if request.user == claim.claimed_by:
                other_user = claim.lost_item.reporter if claim.lost_item else claim.found_item.finder
            elif claim.lost_item and request.user == claim.lost_item.reporter:
                other_user = claim.claimed_by
            elif claim.found_item and request.user == claim.found_item.finder:
                other_user = claim.claimed_by

            if other_user: # Karşı taraf belirlenebiliyorsa
                unread_count = Message.objects.filter(
                    claim=claim, receiver=request.user, is_read=False
                ).count()
                conversations.append({
                    'claim': claim,
                    'last_message': last_message,
                    'other_user': other_user,
                    'unread_count': unread_count
                })

    conversations.sort(key=lambda x: x['last_message'].timestamp, reverse=True)
    return render(request, 'items/messages/inbox.html', {
        'conversations': conversations,
        'page_title': 'Mesaj Kutum'
        })


class SolvedItemsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'items/admin/solved_items.html'
    context_object_name = 'solved_items_list' # Değişiklik: 'solved_items' yerine
    paginate_by = 15

    def test_func(self):
        return is_staff_or_admin(self.request.user)

    def get_queryset(self):
        lost_items = LostItem.objects.filter(status='solved').select_related('reporter', 'solved_by_claim__claimed_by', 'category').order_by('-solved_date')
        found_items = FoundItem.objects.filter(status='solved').select_related('finder', 'solved_by_claim__claimed_by', 'category').order_by('-solved_date')

        all_solved = []
        for item in lost_items:
            all_solved.append({
                'type': 'lost', 'item_type_display': 'Kayıp Eşya',
                'item': item, 'item_name': item.name, 'category': item.category,
                'solved_date': item.solved_date,
                'item_owner': item.reporter, # Kaybeden
                'other_party': item.solved_by_claim.claimed_by if item.solved_by_claim else None, # Bulan/Talep Eden
                'claim': item.solved_by_claim,
                'location': item.lost_location, 'date': item.lost_date,
            })
        for item in found_items:
            all_solved.append({
                'type': 'found', 'item_type_display': 'Bulunan Eşya',
                'item': item, 'item_name': item.name, 'category': item.category,
                'solved_date': item.solved_date,
                'item_owner': item.solved_by_claim.claimed_by if item.solved_by_claim else None, # Sahibi/Talep Eden
                'other_party': item.finder, # Bulan
                'claim': item.solved_by_claim,
                'location': 'Gizli (Güvenlik)', 'date': item.found_date,
            })
        # Tarihe göre birleştirilmiş listeyi sırala
        all_solved.sort(key=lambda x: x['solved_date'] if x['solved_date'] else x['item'].created_at, reverse=True)
        return all_solved

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_solved'] = LostItem.objects.filter(status='solved').count() + FoundItem.objects.filter(status='solved').count()
        context['solved_lost_items_count'] = LostItem.objects.filter(status='solved').count() # Değişiklik
        context['solved_found_items_count'] = FoundItem.objects.filter(status='solved').count() # Değişiklik
        context['page_title'] = 'Çözümlenen İlanlar'
        return context

class SolvedItemDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    template_name = 'items/admin/solved_item_detail.html' # Bu template'i oluşturmanız gerekebilir.
    context_object_name = 'solved_item_data' # Değişiklik

    def test_func(self):
        return is_staff_or_admin(self.request.user)

    def get_object(self):
        item_type = self.kwargs.get('item_type')
        item_id = self.kwargs.get('pk')
        item_obj = None
        data = {'type': item_type}

        if item_type == 'lost':
            item_obj = get_object_or_404(LostItem, pk=item_id, status='solved')
            data.update({
                'item': item_obj,
                'item_owner': item_obj.reporter,
                'other_party': item_obj.solved_by_claim.claimed_by if item_obj.solved_by_claim else None,
                'claim': item_obj.solved_by_claim,
                'item_type_display': 'Kayıp Eşya'
            })
        elif item_type == 'found':
            item_obj = get_object_or_404(FoundItem, pk=item_id, status='solved')
            data.update({
                'item': item_obj,
                'item_owner': item_obj.solved_by_claim.claimed_by if item_obj.solved_by_claim else None,
                'other_party': item_obj.finder,
                'claim': item_obj.solved_by_claim,
                'item_type_display': 'Bulunan Eşya'
            })
        else:
            raise Http404("Geçersiz eşya tipi.")
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solved_item_data = context['solved_item_data']
        if solved_item_data.get('claim'):
            context['messages_list'] = Message.objects.filter(claim=solved_item_data['claim']).order_by('timestamp')
        context['page_title'] = f"Çözümlenen: {solved_item_data['item'].name}"
        return context


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
            # Okunmamış mesaj sayısını context'e ekle
            context['unread_messages_count'] = Message.objects.filter(receiver=self.request.user, is_read=False).count()

        context['categories'] = ItemCategory.objects.all()
        context['page_title'] = 'Ana Sayfa'
        return context

def register(request):
    if request.user.is_authenticated: # Zaten giriş yapmış kullanıcıyı ana sayfaya yönlendir
        return redirect('home')
    if request.method == 'POST':
        u_form = UserRegisterForm(request.POST)
        p_form = UserProfileForm(request.POST) # UserProfileForm'u da al
        if u_form.is_valid() and p_form.is_valid():
            user = u_form.save()
            # UserProfile oluştur
            profile = p_form.save(commit=False)
            profile.user = user
            # Varsayılan kullanıcı tipini 'regular' olarak ayarla (modelde default var ama burada da belirtilebilir)
            profile.user_type = 'regular'
            profile.save()

            login(request, user) # Kullanıcıyı otomatik giriş yap
            messages.success(request, 'Hesabınız başarıyla oluşturuldu! Hoş geldiniz.')
            return redirect('home')
        else:
            # Hataları birleştir
            error_list = []
            for field, errors in u_form.errors.items():
                for error in errors: error_list.append(f"{u_form.fields[field].label or field}: {error}")
            for field, errors in p_form.errors.items():
                for error in errors: error_list.append(f"{p_form.fields[field].label or field}: {error}")
            if error_list:
                messages.error(request, f"Kayıt başarısız. Lütfen hataları düzeltin: {'; '.join(error_list)}")
            else:
                messages.error(request, 'Kayıt başarısız. Lütfen formdaki hataları kontrol edin.')
    else:
        u_form = UserRegisterForm()
        p_form = UserProfileForm()
    return render(request, 'registration/register.html', {
        'u_form': u_form,
        'p_form': p_form,
        'page_title': 'Kayıt Ol'
        })


class LostItemListView(ListView):
    model = LostItem
    template_name = 'items/lost_items/list.html'
    context_object_name = 'lost_items'
    paginate_by = 10
    def get_queryset(self):
        return LostItem.objects.filter(status='lost').select_related('category', 'reporter').order_by('-created_at')
    def get_context_data(self, **kwargs): # Dinamik başlık için
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Kayıp Eşyalar'
        return context

class LostItemDetailView(DetailView):
    model = LostItem
    template_name = 'items/lost_items/detail.html'
    context_object_name = 'item'
    def get_queryset(self): # Performans için ilgili modelleri önceden çek
        return super().get_queryset().select_related('category', 'reporter')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['can_claim'] = (self.object.status == 'lost' and self.object.reporter != self.request.user)
            context['existing_claim'] = Claim.objects.filter(lost_item=self.object, claimed_by=self.request.user).first()
            context['claim_button_text'] = "Bu Eşyayı Buldum - Teslim Etmek İstiyorum"
        context['page_title'] = f"Kayıp: {self.object.name}"
        return context

class LostItemCreateView(LoginRequiredMixin, CreateView):
    model = LostItem
    form_class = LostItemForm
    template_name = 'items/lost_items/create.html'
    # success_url = reverse_lazy('lost-items') # form_valid içinde redirect daha iyi kontrol sağlar

    def form_valid(self, form):
        form.instance.reporter = self.request.user
        messages.success(self.request, 'Kayıp eşya bildirimi başarıyla oluşturuldu.')
        # return super().form_valid(form) # Bunun yerine doğrudan redirect
        item = form.save()
        return redirect(item.get_absolute_url()) # Detay sayfasına yönlendir
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Kayıp Eşya Bildir'
        return context

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
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Düzenle: {self.object.name}"
        return context


class LostItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = LostItem
    template_name = 'items/lost_items/delete.html'
    success_url = reverse_lazy('lost-items')
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.reporter or is_staff_or_admin(self.request.user)
    def form_valid(self, form): # delete yerine form_valid (DeleteView için)
        messages.success(self.request, f"'{self.object.name}' adlı kayıp eşya bildirimi başarıyla silindi.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Sil: {self.object.name}"
        return context


class FoundItemListView(ListView):
    model = FoundItem
    template_name = 'items/found_items/list.html'
    context_object_name = 'found_items'
    paginate_by = 10
    def get_queryset(self):
        return FoundItem.objects.filter(status='available').select_related('category', 'finder').order_by('-created_at')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Bulunan Eşyalar'
        return context

class FoundItemDetailView(DetailView):
    model = FoundItem
    template_name = 'items/found_items/detail.html'
    context_object_name = 'item'
    def get_queryset(self):
        return super().get_queryset().select_related('category', 'finder')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['can_claim'] = (self.object.status == 'available' and self.object.finder != self.request.user)
            context['existing_claim'] = Claim.objects.filter(found_item=self.object, claimed_by=self.request.user).first()
            context['claim_button_text'] = "Bu Benim Eşyam - Talep Ediyorum"
        context['page_title'] = f"Bulunan: {self.object.name}"
        return context

class FoundItemCreateView(LoginRequiredMixin, CreateView):
    model = FoundItem
    form_class = FoundItemForm
    template_name = 'items/found_items/create.html'
    # success_url = reverse_lazy('found-items')

    def form_valid(self, form):
        form.instance.finder = self.request.user
        messages.success(self.request, 'Bulunan eşya bildirimi başarıyla oluşturuldu.')
        item = form.save()
        return redirect(item.get_absolute_url())
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Bulunan Eşya Bildir'
        return context

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
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Düzenle: {self.object.name}"
        return context

class FoundItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = FoundItem
    template_name = 'items/found_items/delete.html'
    success_url = reverse_lazy('found-items')
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.finder or is_staff_or_admin(self.request.user)
    def form_valid(self, form):
        messages.success(self.request, f"'{self.object.name}' adlı bulunan eşya bildirimi başarıyla silindi.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Sil: {self.object.name}"
        return context


class ClaimListView(LoginRequiredMixin, ListView):
    model = Claim
    template_name = 'items/claims/list.html'
    context_object_name = 'claims'
    paginate_by = 10
    def get_queryset(self):
        user = self.request.user
        if is_staff_or_admin(user):
            return Claim.objects.select_related('lost_item', 'found_item', 'claimed_by').order_by('-claim_date')
        else:
            # Kullanıcının hem talep ettiği hem de eşya sahibi olduğu talepleri göster
            return Claim.objects.filter(
                Q(claimed_by=user) |
                Q(lost_item__reporter=user) |
                Q(found_item__finder=user)
            ).distinct().select_related('lost_item', 'found_item', 'claimed_by').order_by('-claim_date')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Taleplerim' if not is_staff_or_admin(self.request.user) else 'Tüm Talepler'
        return context

class ClaimDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Claim
    template_name = 'items/claims/detail.html'
    context_object_name = 'claim'
    def get_queryset(self):
        return super().get_queryset().select_related(
            'lost_item__reporter', 'lost_item__category',
            'found_item__finder', 'found_item__category',
            'claimed_by__userprofile'
        )
    def test_func(self):
        claim = self.get_object()
        user = self.request.user
        return (user == claim.claimed_by or
                (claim.lost_item and user == claim.lost_item.reporter) or
                (claim.found_item and user == claim.found_item.finder) or
                is_staff_or_admin(user))
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_staff_or_admin_user'] = is_staff_or_admin(self.request.user) # Template'de farklı isim
        if context['is_staff_or_admin_user']:
            context['admin_form'] = ClaimAdminForm(instance=self.object)
        context['page_title'] = f"Talep Detayı: #{self.object.pk}"
        return context

@login_required
def create_claim_for_lost_item(request, pk):
    lost_item = get_object_or_404(LostItem, pk=pk, status='lost') # Sadece 'lost' durumdakilere talep
    if request.user == lost_item.reporter: # Kendi eşyasına talep oluşturamasın
        messages.warning(request, "Kendi kayıp eşyanız için teslim talebi oluşturamazsınız.")
        return redirect('lost-item-detail', pk=pk)

    existing_claim = Claim.objects.filter(lost_item=lost_item, claimed_by=request.user).first()
    if existing_claim:
        messages.info(request, 'Bu eşya için zaten bir teslim talebiniz var. Mesajlaşma üzerinden devam edebilirsiniz.')
        return redirect('view-conversation', claim_id=existing_claim.pk)

    if request.method == 'POST':
        form = ClaimForm(request.POST)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.lost_item = lost_item
            claim.claimed_by = request.user
            claim.status = 'pending' # Varsayılan durum
            claim.save()
            Message.objects.create(
                sender=request.user, receiver=lost_item.reporter, claim=claim,
                content=f"Merhaba, '{lost_item.name}' adlı kayıp eşyanızı bulduğumu düşünüyorum. Detay: {claim.claim_description}"
            )
            messages.success(request, 'Teslim talebiniz başarıyla oluşturuldu. Eşya sahibiyle mesajlaşabilirsiniz.')
            return redirect('view-conversation', claim_id=claim.pk)
    else:
        form = ClaimForm()
        form.fields['claim_description'].widget.attrs['placeholder'] = 'Bu eşyayı nerede ve nasıl bulduğunuzu, eşyanın size ait olduğunu düşündüren detayları vb. açıklayın...'


    return render(request, 'items/claims/create.html', {
        'form': form, 'item': lost_item, 'item_type': 'lost',
        'action_type': 'teslim etme', 'page_title': f"Talep Oluştur: {lost_item.name}"
    })

@login_required
def create_claim_for_found_item(request, pk):
    found_item = get_object_or_404(FoundItem, pk=pk, status='available') # Sadece 'available' durumdakilere talep
    if request.user == found_item.finder: # Kendi bulduğu eşyaya talep oluşturamasın
        messages.warning(request, "Kendi bulduğunuz eşya için sahiplik talebi oluşturamazsınız.")
        return redirect('found-item-detail', pk=pk)

    existing_claim = Claim.objects.filter(found_item=found_item, claimed_by=request.user).first()
    if existing_claim:
        messages.info(request, 'Bu eşya için zaten bir sahiplik talebiniz var. Mesajlaşma üzerinden devam edebilirsiniz.')
        return redirect('view-conversation', claim_id=existing_claim.pk)

    if request.method == 'POST':
        form = ClaimForm(request.POST)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.found_item = found_item
            claim.claimed_by = request.user
            claim.status = 'pending'
            claim.save()
            Message.objects.create(
                sender=request.user, receiver=found_item.finder, claim=claim,
                content=f"Merhaba, '{found_item.name}' adlı bulduğunuz eşyanın bana ait olduğunu düşünüyorum. Detay: {claim.claim_description}"
            )
            messages.success(request, 'Sahiplik talebiniz başarıyla oluşturuldu. Eşyayı bulan kişiyle mesajlaşabilirsiniz.')
            return redirect('view-conversation', claim_id=claim.pk)
    else:
        form = ClaimForm()
        form.fields['claim_description'].widget.attrs['placeholder'] = 'Bu eşyanın size ait olduğunu kanıtlayacak detayları (renk, marka, ayırt edici özellikler vb.) açıklayın...'

    return render(request, 'items/claims/create.html', {
        'form': form, 'item': found_item, 'item_type': 'found',
        'action_type': 'sahiplik', 'page_title': f"Talep Oluştur: {found_item.name}"
    })

@login_required
def delete_conversation(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id)
    can_delete = (request.user == claim.claimed_by or
                  (claim.lost_item and request.user == claim.lost_item.reporter) or
                  (claim.found_item and request.user == claim.found_item.finder) or
                  is_staff_or_admin(request.user))
    if not can_delete:
        raise PermissionDenied("Bu sohbeti silme yetkiniz yok.")

    other_user = None
    if request.user == claim.claimed_by:
        other_user = claim.lost_item.reporter if claim.lost_item else claim.found_item.finder
    else: # Eşya sahibi veya admin
        other_user = claim.claimed_by


    if request.method == 'POST':
        messages_count = Message.objects.filter(claim=claim).count()
        Message.objects.filter(claim=claim).delete() # Tüm mesajları sil
        # İsteğe bağlı: Claim'i silmek yerine "archived" gibi bir duruma getirebilirsiniz.
        # claim.status = 'archived_by_user' # Örnek
        # claim.save()
        messages.success(request, f"'{other_user.username if other_user else 'Bilinmeyen Kullanıcı'}' ile olan sohbet ({messages_count} mesaj) başarıyla silindi.")
        return redirect('message-inbox')

    return render(request, 'items/messages/delete_conversation.html', {
        'claim': claim,
        'other_user': other_user,
        'messages_count': Message.objects.filter(claim=claim).count(),
        'page_title': 'Sohbeti Sil Onayı'
    })

@login_required
def delete_conversation_ajax(request, claim_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Sadece POST isteği kabul edilir.'}, status=405)
    claim = get_object_or_404(Claim, pk=claim_id)
    can_delete = (request.user == claim.claimed_by or
                  (claim.lost_item and request.user == claim.lost_item.reporter) or
                  (claim.found_item and request.user == claim.found_item.finder) or
                  is_staff_or_admin(request.user))
    if not can_delete:
        return JsonResponse({'success': False, 'error': 'Bu sohbeti silme yetkiniz yok.'}, status=403)
    try:
        messages_count = Message.objects.filter(claim=claim).count()
        Message.objects.filter(claim=claim).delete()
        return JsonResponse({
            'success': True,
            'message': f'Sohbet başarıyla silindi ({messages_count} mesaj). Sayfa yenileniyor...',
            'redirect_url': reverse('message-inbox')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def update_claim_status(request, pk): # Bu sadece admin/staff için
    claim = get_object_or_404(Claim, pk=pk)
    if not is_staff_or_admin(request.user):
        raise PermissionDenied("Talep durumunu sadece yetkili personel güncelleyebilir.")

    if request.method == 'POST':
        form = ClaimAdminForm(request.POST, instance=claim)
        if form.is_valid():
            updated_claim = form.save()
            # Eğer admin talebi onaylarsa, eşyanın durumunu da güncelle (eşya sahibinin onayı beklenmeden)
            if updated_claim.status == 'approved':
                item_to_solve = updated_claim.lost_item or updated_claim.found_item
                if item_to_solve and item_to_solve.status != 'solved': # Zaten çözülmemişse
                    item_to_solve.status = 'solved' # Admin onayı doğrudan çözüldü yapar
                    item_to_solve.solved_date = timezone.now()
                    item_to_solve.solved_by_claim = updated_claim
                    item_to_solve.save()
                    messages.info(request, f"'{item_to_solve.name}' adlı eşya 'Çözümlendi' olarak işaretlendi.")

            messages.success(request, 'Talep durumu başarıyla güncellendi.')
            return redirect('claim-detail', pk=claim.pk)
    else:
        form = ClaimAdminForm(instance=claim)
    return render(request, 'items/claims/update_status.html', {
        'form': form, 'claim': claim, 'page_title': f"Talep Durumunu Güncelle: #{claim.pk}"
    })

class ClaimDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Claim
    template_name = 'items/claims/delete.html'
    success_url = reverse_lazy('claims')
    def test_func(self): # Sadece talep sahibi veya admin/staff silebilir
        claim = self.get_object()
        return self.request.user == claim.claimed_by or is_staff_or_admin(self.request.user)
    def form_valid(self, form):
        # Talep silinmeden önce ilgili mesajları da silmek iyi bir pratik olabilir
        Message.objects.filter(claim=self.object).delete()
        messages.success(self.request, f"#{self.object.pk} numaralı talep başarıyla silindi.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Talebi Sil: #{self.object.pk}"
        return context


class CategoryListView(ListView):
    model = ItemCategory
    template_name = 'items/categories/list.html'
    context_object_name = 'categories'
    paginate_by = 12
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Eşya Kategorileri'
        return context

class CategoryDetailView(DetailView):
    model = ItemCategory
    template_name = 'items/categories/detail.html'
    context_object_name = 'category'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.object
        context['lost_items'] = LostItem.objects.filter(category=category, status='lost').order_by('-created_at')[:10]
        context['found_items'] = FoundItem.objects.filter(category=category, status='available').order_by('-created_at')[:10]
        context['page_title'] = f"Kategori: {category.name}"
        return context

class CategoryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ItemCategory
    form_class = ItemCategoryForm
    template_name = 'items/categories/create.html'
    success_url = reverse_lazy('categories')
    def test_func(self): return is_staff_or_admin(self.request.user)
    def form_valid(self, form):
        messages.success(self.request, f"'{form.instance.name}' kategorisi başarıyla oluşturuldu.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Yeni Kategori Oluştur'
        return context

class CategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ItemCategory
    form_class = ItemCategoryForm
    template_name = 'items/categories/update.html'
    # success_url = reverse_lazy('categories') # Detaya yönlendirmek daha iyi
    def get_success_url(self):
        return reverse_lazy('category-detail', kwargs={'pk': self.object.pk})
    def test_func(self): return is_staff_or_admin(self.request.user)
    def form_valid(self, form):
        messages.success(self.request, f"'{form.instance.name}' kategorisi başarıyla güncellendi.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Düzenle: {self.object.name}"
        return context

class CategoryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ItemCategory
    template_name = 'items/categories/delete.html'
    success_url = reverse_lazy('categories')
    def test_func(self): return is_staff_or_admin(self.request.user)
    def form_valid(self, form):
        # Kategori silinirse, bu kategoriye bağlı eşyaların kategorisini null yapmak veya
        # varsayılan bir kategoriye atamak gerekebilir. Modelde on_delete=models.SET_NULL veya PROTECT kullanılabilir.
        # Şu anki modelde on_delete=models.CASCADE olduğu için bağlı eşyalar da silinir. Bu istenmiyorsa model güncellenmeli.
        messages.success(self.request, f"'{self.object.name}' kategorisi silindi.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Sil: {self.object.name}"
        return context


def search_view(request):
    form = SearchForm(request.GET or None)
    lost_items_results = LostItem.objects.none() # Başlangıçta boş queryset
    found_items_results = FoundItem.objects.none() # Başlangıçta boş queryset
    search_performed_flag = False # Arama yapılıp yapılmadığını tutar

    if form.is_valid():
        search_term = form.cleaned_data.get('search_term', '').strip()
        category = form.cleaned_data.get('category')
        location = form.cleaned_data.get('location', '').strip()
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        search_type = form.cleaned_data.get('search_type')

        # Eğer en az bir arama kriteri girilmişse arama yapıldı say
        if any([search_term, category, location, date_from, date_to]):
            search_performed_flag = True

            if search_type in ['lost', 'all']:
                query_lost = Q(status='lost') # Sadece aktif kayıp ilanları
                if search_term:
                    query_lost &= (Q(name__icontains=search_term) | Q(description__icontains=search_term))
                if category:
                    query_lost &= Q(category=category)
                if location: # Kayıp eşyalarda lost_location aranır
                    query_lost &= Q(lost_location__icontains=location)
                if date_from:
                    query_lost &= Q(lost_date__gte=date_from)
                if date_to:
                    query_lost &= Q(lost_date__lte=date_to)
                lost_items_results = LostItem.objects.filter(query_lost).select_related('category', 'reporter').order_by('-lost_date', '-created_at')

            if search_type in ['found', 'all']:
                query_found = Q(status='available') # Sadece aktif bulunan ilanları
                if search_term:
                    query_found &= (Q(name__icontains=search_term) | Q(description__icontains=search_term))
                if category:
                    query_found &= Q(category=category)
                # Bulunan eşyalarda 'location' alanı CSV import dışında doğrudan aranmaz (güvenlik nedeniyle kaldırılmıştı)
                # Eğer 'location' girildiyse ve arama tipi 'found' veya 'all' ise, bu kriteri bulunan eşyalar için es geçebiliriz
                # ya da `description` içinde arayabiliriz. Şimdilik es geçiyoruz.
                if date_from:
                    query_found &= Q(found_date__gte=date_from)
                if date_to:
                    query_found &= Q(found_date__lte=date_to)
                found_items_results = FoundItem.objects.filter(query_found).select_related('category', 'finder').order_by('-found_date', '-created_at')
    else: # Form geçerli değilse (genellikle GET ile ilk yükleme)
        search_performed_flag = False


    return render(request, 'items/search.html', {
        'form': form,
        'lost_items': lost_items_results, # Template'deki isimle eşleşmeli
        'found_items': found_items_results, # Template'deki isimle eşleşmeli
        'search_performed': search_performed_flag, # Template'e bu bilgiyi gönder
        'page_title': 'Eşya Arama'
    })


@login_required
def import_export_view(request):
    if not is_staff_or_admin(request.user):
        raise PermissionDenied("Bu sayfaya erişim yetkiniz yok.")

    import_form = CSVImportForm() # Her zaman formu context'e gönder

    if request.method == 'POST':
        # Export işlemleri
        if 'export_lost' in request.POST:
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig') # BOM ile
            response['Content-Disposition'] = f'attachment; filename="kayip_esyalar_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Ad', 'Açıklama', 'Kategori Adı', 'Kayıp Tarihi (GG.AA.YYYY)', 'Kaybolduğu Yer', 'İletişim Bilgisi', 'Durum', 'Bildiren KullanıcıAdı', 'Oluşturulma Tarihi'])
            for item in LostItem.objects.all().select_related('category', 'reporter'):
                writer.writerow([
                    item.name, item.description, item.category.name,
                    item.lost_date.strftime('%d.%m.%Y') if item.lost_date else '',
                    item.lost_location, item.contact_info, item.get_status_display(),
                    item.reporter.username, item.created_at.strftime('%d.%m.%Y %H:%M')
                ])
            return response

        elif 'export_found' in request.POST:
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="bulunan_esyalar_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Ad', 'Açıklama', 'Kategori Adı', 'Bulunma Tarihi (GG.AA.YYYY)', 'Durum', 'Bulan KullanıcıAdı', 'Oluşturulma Tarihi'])
            for item in FoundItem.objects.all().select_related('category', 'finder'):
                writer.writerow([
                    item.name, item.description, item.category.name,
                    item.found_date.strftime('%d.%m.%Y') if item.found_date else '',
                    item.get_status_display(), item.finder.username,
                    item.created_at.strftime('%d.%m.%Y %H:%M')
                ])
            return response

        elif 'export_categories' in request.POST:
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="kategoriler_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Ad', 'Açıklama', 'İkon'])
            for category in ItemCategory.objects.all():
                writer.writerow([category.name, category.description, category.icon])
            return response

        # Import işlemleri
        elif 'import_csv' in request.POST: # Buton name'ini değiştirdim
            import_form = CSVImportForm(request.POST, request.FILES)
            if import_form.is_valid():
                csv_file = import_form.cleaned_data['csv_file']
                import_type = import_form.cleaned_data['import_type']
                success_count = 0
                error_count = 0
                error_details = []

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
                    if not decoded_content: # Eğer hiçbir encoding işe yaramazsa
                        messages.error(request, "CSV dosyasının karakter kodlaması tanınamadı.")
                        return redirect('import-export')


                    reader = csv.DictReader(io.StringIO(decoded_content))
                    
                    # Başlıkları normalize et (Türkçe karakterleri de düşünerek)
                    normalized_fieldnames = {
                        (h.lower().strip()
                         .replace('ı', 'i').replace('ş', 's').replace('ğ', 'g')
                         .replace('ü', 'u').replace('ö', 'o').replace('ç', 'c')): h
                        for h in reader.fieldnames if h
                    }


                    for row_num, row_dict in enumerate(reader, start=2):
                        # Satırdaki başlıkları normalize edilmiş olanlarla eşleştir
                        row = {norm_h: row_dict[orig_h] for norm_h, orig_h in normalized_fieldnames.items() if orig_h in row_dict}

                        try:
                            if import_type == 'lost':
                                cat_name = row.get('kategori') or row.get('category')
                                if not cat_name: raise ValueError("Kategori adı eksik.")
                                category, _ = ItemCategory.objects.get_or_create(
                                    name__iexact=cat_name.strip(),
                                    defaults={'name': cat_name.strip(), 'description': f"{cat_name.strip()} (Oto.)", 'icon': '🏷️'}
                                )
                                date_str = row.get('tarih') or row.get('kayip tarihi') or row.get('lost_date')
                                if not date_str: raise ValueError("Kayıp tarihi eksik.")
                                lost_date_obj = datetime.strptime(date_str.strip(), '%d.%m.%Y').date()

                                LostItem.objects.create(
                                    name=row.get('ad', '').strip(),
                                    description=row.get('aciklama', '').strip(),
                                    category=category,
                                    lost_date=lost_date_obj,
                                    lost_location=row.get('yer', row.get('konum', '')).strip(),
                                    contact_info=row.get('iletisim', '').strip(),
                                    reporter=request.user, status='lost'
                                )
                                success_count += 1
                            elif import_type == 'found':
                                cat_name = row.get('kategori') or row.get('category')
                                if not cat_name: raise ValueError("Kategori adı eksik.")
                                category, _ = ItemCategory.objects.get_or_create(
                                    name__iexact=cat_name.strip(),
                                    defaults={'name': cat_name.strip(), 'description': f"{cat_name.strip()} (Oto.)", 'icon': '🏷️'}
                                )
                                date_str = row.get('tarih') or row.get('bulunma tarihi') or row.get('found_date')
                                if not date_str: raise ValueError("Bulunma tarihi eksik.")
                                found_date_obj = datetime.strptime(date_str.strip(), '%d.%m.%Y').date()

                                FoundItem.objects.create(
                                    name=row.get('ad', '').strip(),
                                    description=row.get('aciklama', '').strip(),
                                    category=category,
                                    found_date=found_date_obj,
                                    finder=request.user, status='available'
                                )
                                success_count += 1
                            elif import_type == 'categories':
                                cat_name = row.get('ad') or row.get('kategori adi')
                                if not cat_name: raise ValueError("Kategori adı eksik.")
                                cat_name = cat_name.strip()
                                if ItemCategory.objects.filter(name__iexact=cat_name).exists():
                                    raise ValueError(f"'{cat_name}' kategorisi zaten mevcut.")
                                ItemCategory.objects.create(
                                    name=cat_name,
                                    description=(row.get('aciklama', row.get('kategori aciklamasi', ''))).strip(),
                                    icon=(row.get('ikon', '🏷️')).strip()
                                )
                                success_count += 1
                        except Exception as e:
                            error_count += 1
                            error_details.append(f"Satır {row_num}: {str(e)} - Veri: {dict(row)}")
                            if error_count > 20: # Çok fazla hata olursa işlemi durdur
                                messages.error(request, "Çok fazla hata oluştu, işlem durduruldu. Lütfen CSV dosyanızı kontrol edin.")
                                break # Döngüden çık

                    if success_count > 0:
                        messages.success(request, f"{success_count} kayıt başarıyla içeri aktarıldı.")
                    if error_count > 0:
                        # Hataları daha okunaklı göster
                        error_summary = f"{error_count} kayıt aktarılamadı. Detaylar (ilk {len(error_details)} hata):"
                        for detail in error_details:
                            error_summary += f"<br>- {detail}"
                        messages.warning(request, error_summary, extra_tags='safe')

                except Exception as e: # Genel dosya işleme hatası
                    messages.error(request, f"CSV dosyası işlenirken bir hata oluştu: {str(e)}")
                return redirect('import-export')
            # else: # Form geçerli değilse, hatalar zaten form üzerinden gösterilecek
            #     pass

    return render(request, 'items/import_export.html', {
        'import_form': import_form,
        'page_title': 'Veri İçeri/Dışarı Aktarma'
    })

def custom_logout(request):
    logout(request)
    messages.info(request, "Başarıyla çıkış yaptınız.")
    return redirect('home')
