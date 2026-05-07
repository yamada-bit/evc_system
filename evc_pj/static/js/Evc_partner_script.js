function getCookie(name) {
  var cookieValue = null;
  if (document.cookie && document.cookie != '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
          var cookie = jQuery.trim(cookies[i]);
          // Does this cookie string begin with the name we want?
          if (cookie.substring(0, name.length + 1) == (name + '=')) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
          }
      }
  }
  return cookieValue;
}
var csrftoken = getCookie('csrftoken');
function csrfSafeMethod(method) {
  // these HTTP methods do not require CSRF protection
  return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}
$.ajaxSetup({
  beforeSend: function(xhr, settings) {
      if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
          xhr.setRequestHeader('X-CSRFToken', csrftoken);
      }
  }
});

// autocomplete を使う処理
function PartnerSearch() {
  // var form = $('#id_form');
  // $.ajax({
  //   url: form.prop('action'),
  //   method: form.prop('method'),
  //   data: form.serialize(),
  //   timeout: 10000,
  //   dataType: 'text',
  // })
  // .done(function(data) {
  //     $('#result').append('<p>' + data + '</p>');
  // })
  var url = $('#id_url').attr('data-url');
  partner_name = $('#id_partner_name').val();
  const partnerElement = $('#id_partner');
  partnerElement.children().remove();
  $.ajax({
    'url': url,
    'type': 'GET',
    'data': {
        'partner_name': partner_name,
    },
    'dataType': 'json'
  })
  .done(function(response){
    // alert(response.plus);    // let html_data = '';
    for (const partner of response.partner_list) {
      const option = $('<option>');
      option.val(partner['name']);
      partnerElement.append(option);
    }
    var data = [];
    for (const partner of response.partner_list) {
      data.push(partner['name']);
    }
    alert(data);
    $('#id_partner_name').autocomplete({
      source: data,
      autoFocus: true,
      delay: 500,
      minLength: 2
    });

  }).fail( function(xhr, status, error) {
    alert(status + ':' + error );
  });
  $('#id_partner_name').trigger('click');
}

// function change_partner() {
//   partner_name = $('#id_partner').val();
//   document.getElementById( 'id_partner_name' ).value = partner_name;
//   $('#modal_dialog').dialog('close');
// }
// 検索ボタンクリックで取引先一覧ダイアログを表示
function PartnerPopup() {
  var url = $('#id_url').attr('data-url');
  partner_name = $('#id_partner_name').val();
  var partnerElement = $('#id_partner');
  partnerElement.children().remove();
  $.ajax({
    'url': url,
    'type': 'GET',
    'data': {
        'partner_name': partner_name,
    },
    'dataType': 'json'
  })
  .done(function(response){
    for (var partner of response.partner_list) {
      var option = $('<option>');
      option.val(partner['id']);
      option.text(partner['name']);
      partnerElement.append(option);
    }
    var w = $('#id_partner_name').width();
    $('#modal_dialog').dialog({
      dialogClass: 'partnerDialog',
      position: {my: 'left top', at: 'left bottom', of: '#id_partner_name'},
      width: w,   
      buttons: {
        '閉じる': function() {
          $( this ).dialog( 'close' );
        }
      }
    });

  }).fail( function(xhr, status, error) {
    alert(status + ':' + error );
  }); 
}
function ClosePartnerPopup() {
   $('#modal_dialog').dialog('close');
}
// $( document ).on( 'click', '.ui-widget-overlay', function(){
//   $('#modal_dialog').dialog('close');
// });
// ダイアログ外をクリックしたら閉じる
$(document).on('click', function(e) {
	if(!$(e.target).closest('#modal_dialog').length){
   $('#modal_dialog').dialog('close');
	}
});

