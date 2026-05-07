const $modal = document.getElementById('del-record');
const $openButton = document.querySelectorAll('#open');
const $closeButton = document.querySelectorAll('#close');
const $deleteButton = document.querySelectorAll('#delete');

let $deleteFlg = false;

for (let i = 0; i < $openButton.length; i++) {
  $openButton[i].addEventListener('click', (e) => {
    // e.stopPropagation();
    // $modal.showModal();
    $deleteFlg = true;
  });
}

// for (let i = 0; i < $openButton.length; i++) {
//   $openButton[i].addEventListener('click', (e) => {
//     e.stopPropagation();
//     // クリックされた要素
//     const clickedElement = e.target;
//     // 親要素を取得
//     let tr = clickedElement.closest('tr');
//     let shared_id = tr.dataset.shared;
//     document.getElementById( 'shared_id' ).value = shared_id;

//     $modal.showModal();
//   });
// }

for (let i = 0; i < $closeButton.length; i++) {
  $closeButton[i].addEventListener('click', () => {
    $modal.close();
  });
}
for (let i = 0; i < $deleteButton.length; i++) {
  $deleteButton[i].addEventListener('click', () => {
    $modal.close();
    delete_evidence_list();
  });
}
// $(function () {
//     $.datepicker.setDefaults($.datepicker.regional["ja"]);
//     $("#date").datepicker();

//     $('#search_form').find('select').change(function () {
//         document.search_form.submit();
//     });

//     $('#per').change(function () {
//         document.search_form.submit();
//     });

// });
$(function() {
  $('tr[data-href]').on('click', function(e) {
      if ($deleteFlg) {
          $deleteFlg = false;
          let str = $(this).data('href');
          let idx = str.indexOf('file_edit');
          let len = 'file_edit'.length;
          let shared_id = str.substring(idx + len + 1, idx + len + 15);
          document.getElementById( 'shared_id' ).value = shared_id;
          $modal.showModal();
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
          3: { sorter: false }, // カテゴリ
          4: { sorter: false }, // 金額
          5: { sorter: false }, // 取引先
      }
  });
});

// $('#id_shared_month').change(function () {
//     let num = document.getElementById( 'select_page_size' ).value;
//     document.getElementById( 'id_page_size' ).value = num;
//     document.getElementById( 'act' ).value = '';
//     var date = $(this).val();
//     document.SearchForm.submit();
// });
function change_page_size() {
    let num = document.getElementById( 'select_page_size' ).value;
    document.getElementById( 'id_page_size' ).value = num;
    document.getElementById( 'act' ).value = '';
    $('#searchForm').submit();
}

function delete_evidence_list() {
  document.getElementById( 'act' ).value = 'del';
  $('#searchForm').submit();
}
