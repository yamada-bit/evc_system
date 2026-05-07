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

function duplicate() {
    var url = $('#id_url').attr('data-url');
    // partner_name = $('#id_partner_name').val();
    $.ajax({
      'url': url,
      'type': 'GET',
      'data': {
          'evidence_id': '',
      },
      'dataType': 'json'
    })
    .done(function(response){
      var info = response.duplicate_info['info'];
      show_message(info);
    }).fail( function(xhr, status, error) {
      alert(status + ':' + error );
    }); 
}
  
// function duplicate() {
//     let info = document.getElementById('duplicate_info').value;
//     show_message(info);
// }
//全クリア
function clear_all()
{
    document.getElementById('id_pdf_name').value = '';
    if (document.getElementById('id_shori_date') != null) {
        document.getElementById('id_shori_date').value = '';
    }
    if (document.getElementById('id_create_date') != null) {
        document.getElementById('id_create_date').value = '';
    }
    document.getElementById('id_category').selectedIndex = 0;
    document.getElementById('id_partner').value = '';
    document.getElementById('id_publisher').value = '';
    document.getElementById('id_process_date1').value = '';
    document.getElementById('id_process_date2').value = '';
    // document.getElementById('id_amount1').value = '';
    // document.getElementById('id_amount2').value = '';
    document.getElementById('id_amount').value = '';
    document.getElementById('id_amount_choice').selectedIndex = 0;
    document.getElementById('id_user_kubuns_0').checked = true;
    document.getElementById('id_today_kubuns_0').checked = true;
    document.getElementById('id_slip_number').value = '';
    
    change_shori_date();
    change_create_date();
}

function PdfList()
{
    document.getElementById( 'act' ).value = 'search';
    document.getElementById( 'id_duplist' ).value = '';
    $('#searchForm').submit();
}

function PdfList_org()
{
    // tableに色を塗る
    function setcolor(classname) {
        let rank = $(classname);

        let arr = [];

        // CSSをつける
        $.each(rank, function(_, v) {
            let value = ($(v).text());
            if (value == 'NG') $(v).css('background-color', 'red');
        });
    }
    setcolor('.result');

    if ((SearchForm.pdf_name.value == '' ) && (SearchForm.shori_date.value == '' ))
    { }
}
function duplicateList() {
    document.getElementById( 'act' ).value = 'duplicate';
    document.getElementById( 'id_duplist' ).value = 'duplist';
    $('#searchForm').submit();
}

$(function() {
    $('tr[data-href]').on('click', function(e) {
        if ($deleteFlg) {
            $deleteFlg = false;
            let str = $(this).data('href');
            let evi_id = str.substr(str.indexOf('sconcreate') + 11);
            document.getElementById( 'evi_id' ).value = evi_id;
            $modal.showModal();
        } else {
            if($(e.target).closest('.prosessing').length==0) {
                location.href = $(this).data('href');
            } else {
                show_message('処理中です。');
            }
        }
    });
    if (document.getElementById('id_shori_date') != null) {
        document.getElementById('id_shori_date').addEventListener('change', function () {change_shori_date();});
        change_shori_date();
    }
    if (document.getElementById('id_create_date') != null) {
        document.getElementById('id_create_date').addEventListener('change', function () {change_create_date();});
        change_create_date();
    }

    // document.getElementById('id_category').addEventListener('change', function() {changeColor(this);});
    // document.getElementById('id_process_date1').addEventListener('change', function() {changeColor(this);});
    // document.getElementById('id_process_date2').addEventListener('change', function() {changeColor(this);});

    $('#ev_table').tablesorter({
        headers: {
            // 0: { sorter: false }, // No.
            1: { sorter: false }, // ファイル名
            2: { sorter: false }, // 処理年月
            3: { sorter: false }, // カテゴリ
            4: { sorter: false }, // 金額
            5: { sorter: false }, // 取引先
            6: { sorter: false }, // 発行元
            // 7: { sorter: false }, // 日付
            8: { sorter: false }  // 結果
        }
    });
});

function change_shori_date() {
    if (document.getElementById('id_shori_date') != null) {
        let shori_date = document.getElementById( 'id_shori_date' );
        let shori_date_val = shori_date.value;
        if (shori_date_val != '') {
            document.getElementById('id_today_kubuns_1').checked = true;
            document.getElementById('id_today_kubuns_0').disabled = true;
        } else {
            document.getElementById('id_today_kubuns_0').disabled = false;
        } 
    }
    // changeColor(elm);
}
function change_create_date() {
    let create_date = document.getElementById( 'id_create_date' );
    let create_date_val = create_date.value;
    if (create_date_val != '') {
        document.getElementById('id_today_kubuns_1').checked = true;
        document.getElementById('id_today_kubuns_0').disabled = true;
    } else {
        document.getElementById('id_today_kubuns_0').disabled = false;
    } 
    // changeColor(elm);
}

function delete_evidence_list() {
    document.getElementById( 'act' ).value = 'del';
    $('#searchForm').submit();
}
function change_page_size() {
    let num = document.getElementById( 'select_page_size' ).value;
    document.getElementById( 'id_page_size' ).value = num;
    document.getElementById( 'act' ).value = '';
    $('#searchForm').submit();
}
jQuery(function ($) {
    $(function () {
        $('#btn_dropdown').click(function (e) {
            e.stopPropagation();
            $('#dropdown').toggleClass('show');
        });
        $(document).on('click', function(e) {
            if ($('#dropdown').hasClass('show')) {
                $('#dropdown').toggleClass('show');
            }
        });
    });
});
