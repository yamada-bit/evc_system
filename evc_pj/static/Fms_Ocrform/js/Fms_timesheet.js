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

//全クリア
function clear_all()
{
    if (document.getElementById('id_office_name') != null) {
        document.getElementById('id_office_name').value = '';
    }
    if (document.getElementById('id_emp_id') != null) {
        document.getElementById('id_emp_id').value = '';
    }
    if (document.getElementById('id_emp_name') != null) {
        document.getElementById('id_emp_name').value = '';
    }
    if (document.getElementById('id_dept') != null) {
        document.getElementById('id_dept').value = '';
    }
    if (document.getElementById('id_section') != null) {
        document.getElementById('id_section').value = '';
    }
    if (document.getElementById('id_spine') != null) {
        document.getElementById('id_spine').value = '';
    }
    if (document.getElementById('id_username') != null) {
        document.getElementById('id_username').value = '';
    }
    // document.getElementById('id_category').selectedIndex = 0;
    // document.getElementById('id_partner').value = '';
    // document.getElementById('id_publisher').value = '';
    document.getElementById('id_process_date1').value = '';
    document.getElementById('id_process_date2').value = '';
    // change_shori_date();
    // change_create_date();
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
            let str_len;
            let idx = str.indexOf('ocrdata_edit/timesheet/');
            if (idx < 0) {
                idx = str.indexOf('ocrdata_edit/ocrdata/');
                if (idx < 0) {
                    idx = str.indexOf('ocrdata_edit/jafyame/');
                    if (idx < 0) {
                        idx = str.indexOf('ocrdata_edit/kumamoto/');
                        if (0 < idx) {
                            str_len = 'ocrdata_edit/kumamoto/'.length
                        }
                    } else if (0 < idx) {
                        str_len = 'ocrdata_edit/jafyame/'.length
                    }
                } else {
                    str_len = 'ocrdata_edit/ocrdata/'.length
                }
            } else {
                str_len = 'ocrdata_edit/timesheet/'.length
            }
            if (0 < idx) {
                let ocrdata_id = str.substring(idx + str_len, idx + str_len + 20);
                document.getElementById( 'ocrdata_id' ).value = ocrdata_id;
                $modal.showModal();
            }
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
