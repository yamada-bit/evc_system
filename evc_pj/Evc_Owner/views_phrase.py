from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import \
    ListView, DetailView, CreateView, UpdateView, DeleteView
from django.shortcuts import get_object_or_404, redirect
from users.models import MtPhrase
from Evc_Owner.forms import PhraseForm

class PhraseListView(ListView):
    template_name = 'Evc_Owner/FE_Phrase_list.html'
    model = MtPhrase
    paginate_by = 10  # 1ページに表示する件数

class PhraseDetailView(DetailView):
    template_name = 'Evc_Owner/FE_Phrase_detail.html'
    model = MtPhrase

class PhraseCreateView(CreateView):
    template_name = 'Evc_Owner/FE_Phrase_form.html'
    model = MtPhrase
    form_class = PhraseForm
    success_url = reverse_lazy('Evc_Owner:phrase_list')

    def get_initial(self):
        initial = super().get_initial()
        initial['phrase_id'] = self.get_next_id()
        return initial
    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, '「{}」を作成しました'.format(form.instance))
        return result
    def get_next_id(self):
        id = 'phrs'
        lastobj = MtPhrase.objects.all().order_by('-phrase_id').first() # first():存在しない場合Noneを返す
        if lastobj:
            pre_id = lastobj.phrase_id
            try:
                num = int(pre_id[-5:])
                id = id + '_{:05d}'.format(num + 1)
            except Exception:   # ValueError
                id = id + '_00001'
        else:
            id = id + '_00001'
        return id
    
class PhraseUpdateView(UpdateView):
    template_name = 'Evc_Owner/FE_Phrase_form.html'
    model = MtPhrase
    form_class = PhraseForm

    success_url = reverse_lazy('Evc_Owner:phrase_list')

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, '「{}」を更新しました'.format(form.instance))
        return result

class PhraseDeleteView(DeleteView):
    template_name = 'Evc_Owner/FE_Phrase_confirm_delete.html'
    model = MtPhrase
    form_class = PhraseForm

    success_url = reverse_lazy('Evc_Owner:phrase_list')

    # def delete(self, request, *args, **kwargs):
    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()
        return HttpResponseRedirect(success_url)
    # def form_invalid(self, form):
    #     print(form.errors)
    #     form.instance.user = self.request.user
    #     return super().form_invalid(form)
    
# 削除確認画面なしで、viewの定義もdefで始まる形（関数ベース汎用ビュー）
def delete(request, pk):
    phrase = get_object_or_404(MtPhrase, phrase_id=pk)
    phrase_id = phrase.phrase_id
    phrase.delete()
    messages.success(
        request, '「{}」を削除しました'.format(phrase_id))
    return redirect('Evc_Owner:phrase_list')