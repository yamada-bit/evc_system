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
    document.getElementById('id_shori_date').value = '';
}

function PdfList()
{
    document.getElementById( 'act' ).value = '';
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

$(function() {
    $('tr[data-href]').on('click', function(e) {
        if ($deleteFlg) {
            $deleteFlg = false;
            let str = $(this).data('href');
            let idx = str.indexOf('edit_entry');
            if (0 < idx) {
                let evi_id = str.substring(idx + 11, idx + 31);
                document.getElementById('ocrdata_id').value = evi_id;
                $modal.showModal();
            } else {
                idx = str.indexOf('ocrdata_edit/entry/');
                if (0 < idx) {
                    let str_len = 'ocrdata_edit/entry/'.length
                    let ocrdata_id = str.substring(idx + str_len, idx + str_len + 20);
                    document.getElementById('ocrdata_id').value = ocrdata_id;
                    $modal.showModal();
                }

            }
        } else {
            if($(e.target).closest('.prosessing').length==0) {
                location.href = $(this).data('href');
            } else {
                show_message('処理中です。');
            }
        }
    });

    $('#ev_table').tablesorter({
        headers: {
            // 0: { sorter: false }, // No.
            1: { sorter: false }, // ファイル名
            2: { sorter: false }, // 処理年月
        }
    });
});

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
