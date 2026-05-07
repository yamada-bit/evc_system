from django.urls import path

from . import views
from . import views_phrase

app_name = 'Evc_Owner' 
urlpatterns = [
    path('edit_owner/', views.EvcEditOwnerView.as_view(), name='edit_owner'),
    path('update_owner/<pk>/', views.EvcUpdateOwnerView.as_view(), name='update_owner'),
    path('owner_list/',views.EvcOwnerListView.as_view(),name='owner_list'),
    # path('selectable_list/',views.EvcSelectableUserListView.as_view(),name='selectable_list'),
    path('phrase_list/',views_phrase.PhraseListView.as_view(),name='phrase_list'),
    path('phrase_detail/<pk>',views_phrase.PhraseDetailView.as_view(),name='phrase_detail'),
    path('phrase_create/',views_phrase.PhraseCreateView.as_view(),name='phrase_create'),
    path('phrase_update/<pk>',views_phrase.PhraseUpdateView.as_view(),name='phrase_update'),
    # path('phrase_delete/<pk>',views_phrase.PhraseDeleteView.as_view(),name='phrase_delete'),
    path('phrase_delete/<pk>',views_phrase.delete,name='phrase_delete'),
]