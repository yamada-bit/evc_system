document.getElementById('commit').addEventListener('click', commit);
document.getElementById('csv_load').addEventListener('click', csv_load);
// document.getElementById('cancel').addEventListener('click', cancel);

const ownerElement = $('#id_owner');
let isEdit = false;
let isSubmit = false;
ownerElement.on('change', () => {
  if (!isEdit && !isSubmit) {
    $('#searchForm').submit();
  }
});
function commit() {
////////////////検索条件をDBに登録/////////////////////////
  if (isSubmit) {
    show_message('処理中です');
    return;
  }
  isSubmit = true;
  document.getElementById( 'submit_action' ).value = 'commit';
  document.getElementById( 'object_list_json' ).value = getTableJson();

  $('#searchForm').submit();
}
function cancel(){
  // window.location.href = "{% url 'Evc_App:evidence_list' %}";
  // history.back();
  // open( 'FE_Evilist.html', '_blank') ;
  // location.replace("{% url 'Evc_App:evidence_list' %}");
  document.getElementById( 'submit_action' ).value = 'cancel';
  $('#searchForm').submit();
}
// 行追加・削除
$('.del-item').click(function() {
  let row = $(this).closest('tr').remove();
  // $(row).remove();
});
$('.ins-item').click(function() {
  let $row = $(this).closest('tr');
  let $newRow = $row.clone(true);
  $newRow.find('input').val('');
  $newRow.insertAfter($row);
});

function getTableJson() {
  let lists = [];
  let idx = 0
  $('table tbody tr').map(function(index, element){
      let user_id = $(element).children().eq(0).children('input').val();
      // let folder_path = $(element).children().eq(1).children('input').val();
      if (user_id && user_id.trim()) {
          // if (area_no && area_no.trim()) {
          //     let num = Number(area_no);
          //     if (num < 1) {
          //         area_no = ''
          //     }
          // } else {    // --1など数値に変換できない場合val()が空白で取得される
          //     area_no = ''
          // }

          lists[idx] = {
              'item_no': '' + (idx + 1)
              ,'user_id':user_id
              // ,'folder_path':folder_path
          };
          idx++;
      }
  });
  let json_str = JSON.stringify(lists);
  return json_str;
}

let fileInput = document.getElementById('csv_file');
let reader = new FileReader();
// ファイル変更時イベント
// fileInput.onchange = () => {
//   let file = fileInput.files[0];
//   reader.readAsText( file );  
// };
function csv_load() {
  let file = fileInput.files[0];
  reader.readAsText( file );  
}
reader.addEventListener('load', function() {
    let line = reader.result.split('\n'); 
    let str=[];
    let str2 = '';
    for(let i = 0; i < line.length; i++){
      str = line[i].split(',');
      if (str[1].indexOf("\"") != -1){
        str2 = str[1].replace(/[\"]/g,"");
      }
      let input1 = '<input type="search" name="id" value="' + str[0] + '">'
      let input2 = '<input type="search" name="path" value="' + str2 + '">'
      // insert = '<tr><td>' + input1 + '</td><td>' + input2 + '</td>\
      insert = '<tr><td>' + input1 + '</td>\
      <td><p class="del-item">ー</p></td><td><p class="ins-item">＋</p></td></tr>';
      document.getElementById('table_tbody').insertAdjacentHTML('beforeend', insert);
    }
    $('.del-item').click(function() {
      let row = $(this).closest('tr').remove();
      // $(row).remove();
    });
    $('.ins-item').click(function() {
      let $row = $(this).closest('tr');
      let $newRow = $row.clone(true);
      $newRow.find('input').val('');
      $newRow.insertAfter($row);
    });
  })
