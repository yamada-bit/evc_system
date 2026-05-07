document.getElementById('commit').addEventListener('click', commit);
document.getElementById('cancel').addEventListener('click', cancel);
document.getElementById('sort_number').addEventListener('click', renumber);
// document.getElementById('delete_ocrform').addEventListener('click', delete_evidence);
document.getElementById('delete_ocrform').addEventListener('click', click_delete);

const $modal = document.getElementById('del-record');
const $closeButton = document.querySelectorAll('#close');
const $scondeleteButton = document.querySelectorAll('#scon_delete');

let isSubmit = false;
let isEdit = false;

let areas = []; // 入力領域図形 { x1:minx,y1:miny,x2:maxx,y2:maxy,text:text }

// 削除ダイアログ表示
function click_delete() {
    if (isSubmit) {
      return;
    }
    $modal.showModal();
}
for (let i = 0; i < $closeButton.length; i++) {
    $closeButton[i].addEventListener('click', () => {
        $modal.close();
    });
}
for (let i = 0; i < $scondeleteButton.length; i++) {
    $scondeleteButton[i].addEventListener('click', () => {
        $modal.close();
        delete_evidence();
    });
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
// function search() {
//     let searchValue = this.value.toLowerCase();
//     let tableRows = document.getElementById('table_item').getElementsByTagName('tr');
    
//     for (let i = 1; i < tableRows.length; i++) {
//         let rowText = tableRows[i].textContent.toLowerCase();
//         if (rowText.indexOf(searchValue) > -1) {
//         tableRows[i].style.display = '';
//         } else {
//         tableRows[i].style.display = 'none';
//         }
//     }
// } 
// function sortRows() {
//     const table = document.querySelector('table');
//     const records = [];
//     for (let i = 1; i < table.rows.length; i++) {
//       const record = {};
//       record.row = table.rows[i];
//       record.key = table.rows[i].cells[this.cellIndex].textContent;
//       records.push(record);
//     }
//     records.sort(compareKeys);
//     for (let i = 0; i < records.length; i++) {
//         table.appendChild(records[i].row);
//       }    
// }
// function compareKeys(a, b) {
//     if (a.key < b.key) return -1;
//     if (a.key > b.key) return 1;
//     return 0;
// }
// let inputs = document.querySelectorAll('input');
// inputs.forEach(input => {
//   input.addEventListener('change', updateValue);
// });        
// function updateValue() {
//     isEdit = true;
// }
function download() {
//////////////////pdfを印刷する///////////////////////////
  let element = document.createElement('a');
  // a要素のhref属性を設定
  element.href = '{{ imgfile }}'
  // // a要素のdownload属性を設定
  element.download = 'sample.png';
  // // a要素のtarget属性を設定
  element.target = '_blank';
  // a要素のクリック実行
  element.click();
}
function commit() {
////////////////検索条件をDBに登録/////////////////////////
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  document.getElementById( 'submit_action1' ).value = 'commit';
  document.getElementById( 'object_list_json' ).value = getTableJson();
  document.getElementById( 'postext' ).value = get_areas();

  $('#form1').submit();
}
function delete_evidence() {
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  document.getElementById( 'submit_action1' ).value = 'delete';
  $('#form1').submit();
}
function cancel() {
//   if (isEdit) {
//     if (isSubmit) {
//       show_message('処理中です');
//       return;
//     }
//     let result = window.confirm('更新が実行されていません。変更内容は破棄されます。\nよろしいですか？');
//     if (!result) {
//       return;
//     }
//   }
  document.getElementById( 'submit_action1' ).value = 'cancel';
  $('#form1').submit();
}
// 表データの名前を取得(重複登録しないように)
function initTable() {
    $('table tbody tr').map(function(index, element){
        // let item_name = $(element).children().eq(0).children('input').val();
        // let area_no = $(element).children().eq(1).children('input').val();
        let item_json = $(element).children().eq(2).children('input').val();
        let table_id = $(element).children().eq(3).children('input').val();
        if (table_id != undefined && item_json != undefined) {
            if (table_id.trim() && item_json == table_id) {
                let idx = table_names.indexOf(table_id);
                if (idx < 0) {
                    table_names.push(table_id);
                }
            }
        }
    });
}
// 表データの最後の列の要素のデータを連想配列で保存
function getLastCol(table_id) {
    let idx = table_names.indexOf(table_id);
    if (idx < 0) {
        return false;
    }
    // 表データの最後の列の名前を取得
    let col_names = [];
    let last_col = '';
    $('table tbody tr').map(function(index, element){
        let item_name = $(element).children().eq(0).children('input').val();
        // let area_no = $(element).children().eq(1).children('input').val();
        let item_json = $(element).children().eq(2).children('input').val();
        let id = $(element).children().eq(3).children('input').val();
        if (id == table_id && item_json != table_id) {
            let name = item_name.substring(0, item_name.lastIndexOf('_'));
            let colidx = col_names.indexOf(name);
            if (colidx < 0) {
                col_names.push(name);
                last_col = name;
            }
        }
    });
    // 表データの最後の列の要素を連想配列で保存
    let cols = {};
    let ret = false;
    $('table tbody tr').map(function(index, element){
        let item_name = $(element).children().eq(0).children('input').val();
        let id = $(element).children().eq(3).children('input').val();
        let lastidx = item_name.lastIndexOf('_');
        if (0 < lastidx) {
            let no = item_name.substring(lastidx + 1);
            let name = item_name.substring(0, lastidx);
            if (id == table_id && name == last_col) {
                cols[no] = element;
                ret = true;
            }
        }
    });
    if (idx < table_cols.length) {
        table_cols[idx] = cols;
    } else {
        table_cols.push(cols);
    }
    return ret;
}
// 表の該当行の後に行挿入
function insertItem(item_name, item_json, table_id, area_no, row_no) {
    let idx = table_names.indexOf(table_id);
    if (idx < 0) {
        return false;
    }
    let $newRow = $('#table_item tbody tr:last-child').clone(true);
    $newRow.find('input').val('');
    $newRow.children().eq(0).children('input').val(item_name);
    $newRow.children().eq(1).children('input').val(area_no);
    $newRow.children().eq(2).children('input').val(item_json);
    $newRow.children().eq(3).children('input').val(table_id);

    let insert = false;
    if (idx < table_cols.length) {
        let cols = table_cols[idx];
        if (String(row_no + 1) in cols) {
            let elm = cols[String(row_no + 1)];
            $newRow.insertAfter(elm);
            insert = true;
        // } else {
        //     for(let key in cols) {
        //         if (row_no < parseInt(key, 10)) {
        //             let elm = cols[key];
        //             $newRow.insertBefore(elm);
        //             insert = true;
        //             break;
        //         }
        //     }
        }
    }
    // 該当行がなければテーブルの最終行に追加
    if (!insert) {
        $newRow.appendTo('#table_item tbody');
    }
}
// テーブルの最後に行追加
function addItem(item_name, item_json, table_id, area_no) {
    let $newRow = $('#table_item tbody tr:last-child').clone(true);
    $newRow.find('input').val('');
    $newRow.appendTo('#table_item tbody');
    $newRow.children().eq(0).children('input').val(item_name);
    $newRow.children().eq(1).children('input').val(area_no);
    $newRow.children().eq(2).children('input').val(item_json);
    $newRow.children().eq(3).children('input').val(table_id);
}

function getTableJson() {
    let lists = [];
    let idx = 0
    $('table tbody tr').map(function(index, element){
        let item_name = $(element).children().eq(0).children('input').val();
        let area_no = $(element).children().eq(1).children('input').val();
        let item_json = $(element).children().eq(2).children('input').val();
        let table_id = $(element).children().eq(3).children('input').val();
        if (item_name && item_name.trim()) {
            if (area_no && area_no.trim()) {
                let num = Number(area_no);
                if (num < 1) {
                    area_no = ''
                }
            } else {    // --1など数値に変換できない場合val()が空白で取得される
                area_no = ''
            }

            lists[idx] = {
                'item_no': '' + (idx + 1)
                ,'item_name':item_name
                ,'area_no':area_no
                ,'item_json':item_json
                ,'table_id':table_id
            };
            idx++;
        }
    });
    let json_str = JSON.stringify(lists);
    return json_str;
}
// 座標データをサーバに返す
function get_areas() {
    if (areas.length < 1)
        return '';
    // outareas = areas
    // if (angle != 0) {
    //     outareas = rotate_pos(outareas, 360 - angle, ocrform_img.height, ocrform_img.width);
    // }
    // JSONデータで返す
    let json_text = JSON.stringify(areas);
    return json_text;
}

// 座標データを並べ替える
function sort_areas() {
    if (areas.length < 1)
        return '';
    areas.sort((a, b) => {
        return a.y1 < b.y1 ? -1 : 1;
    });
    let outareas = [];
    let areasy1 = areas.slice();
    // 矩形をY座標で並べ替える
    // 矩形の半分より上か下かで分割
    // 最大5分割
    for (let i = 0; i < 5; i++){
        areasy1 = sort_y(areasy1, outareas)
        if (areasy1.length == 0) {
            break;
        }
    }
    // 最終エリアをx座標でソート
    if (0 < areasy1.length) {
        areasy1.sort((a, b) => {
            return a.x1 < b.x1 ? -1 : 1;
        });
        for (let p of areasy1) {
            outareas.push(p);
        }
    }
    // if (angle != 0) {
    //     outareas = rotate_pos(outareas, 360 - angle, ocrform_img.height, ocrform_img.width);
    // }
    return outareas;
}
function sort_y(areas0, areas1) {
    let idx = 0;
    let areasy1 = [];
    let areasy2 = [];
    for (let p of areas0) {
        if (idx== 0) {
            pre_y = (p.y2 + p.y1) / 2;
            areasy1.push(p);
        } else {
            if (pre_y < p.y1)
                areasy2.push(p);
            else
                areasy1.push(p);
        }
        idx++;
    }
    // エリアをx座標でソート
    areasy1.sort((a, b) => {
        return a.x1 < b.x1 ? -1 : 1;
    });
    for (let p of areasy1)
        areas1.push(p);
    return areasy2;
}
function renumber() {
    let newareas = [];
    let news = [];
    let new_no = 1;
    // 表の上から順に領域番号で設定されている領域情報を複製し連番を設定、領域番号は保存
    $('table tbody tr').map(function(index, element) {
        let item_name = $(element).children().eq(0).children('input').val();
        let area_no = $(element).children().eq(1).children('input').val();
        // let item_json = $(element).children().eq(2).children('input').val();
        // let table_id = $(element).children().eq(3).children('input').val();
        if (item_name && item_name.trim()) {
            if (area_no && area_no.trim()) {
                let num = Number(area_no);
                if (num != 0) {
                    let index = areas.findIndex(object => Number(object.text) === num);
                    if (index < 0) {
                        $(element).children().eq(1).children('input').val('');
                    } else {
                        $(element).children().eq(1).children('input').val('' + new_no);
                        let clone = Object.assign({}, areas[index]);    // オブジェクトの複製を作成
                        let text =  String(new_no);
                        clone.text = text;
                        newareas.push(clone);
                        news.push(num);
                        new_no++;
                    }
                }
            } else {    // --1など数値に変換できない場合val()が空白で取得される
                $(element).children().eq(1).children('input').val('');
            }
        } else {
            $(element).children().eq(1).children('input').val('');
        }
    });
    // let area_no = 1;
    // for (let no of news) {
    //     let index = areas.findIndex(object => Number(object.text) === no);
    //     if (0 <= index) {
    //         let clone = Object.assign({}, areas[index]);
    //         let text =  String(area_no);
    //         clone.text = text;
    //         newareas.push(clone);
    //         area_no++;
    //     }
    // }

    // 保存されていない領域情報を複製し連番を設定
    for (let obj of areas) {
        let num = Number(obj.text);
        let result = false;
        if (!isNaN(num)) {
            result = news.includes(num);
        }
        if (!result) {
            let clone = Object.assign({}, obj);
            let text =  String(new_no);
            clone.text = text;
            newareas.push(clone);
            new_no++;
        }
    }
    // 複製した領域情報を領域情報にコピー(配列を別オブジェクトで作成)
    areas = newareas.slice();   // 別オブジェクトで作成
    area_no_max = new_no - 1;
    draw();
    // for (const [idx, p] of areas.entries()) {
    //     areanumber = String(idx + 1);
    // }
}
// document.getElementById('cancel').addEventListener('click', cancel);
$(document).on('click', 'a', function(e) {
  let id = e.currentTarget.id;
  if (id == 'back_btn' || id == 'next_btn') {
    e.preventDefault();
    let href = $(this).attr('href');
    if (href !== undefined) {
      // let saved = '{{ saved }}';
      // if (isEdit) {
      //   show_confirm('領域が保存されていません。ページ移動してよろしいですか？', href);
      // } else {
      //   location.href = href;
      // }
      isEdit = true;
      if (isEdit) {
        if (isSubmit) {
          show_message('処理中です');
        } else {
          isSubmit = true;
          document.getElementById( 'object_list_json' ).value = getTableJson();
          document.getElementById( 'postext' ).value = get_areas();
          document.getElementById( 'submit_action1' ).value = id;
          document.getElementById( 'id_pagebtn' ).value = id;
          $('#form1').submit();
        }
      } else {
        location.href = href;
      }
      // let result = window.confirm('領域保存が実行されていません。よろしいですか？');
      // if (result) {
      //   location.href = href;
      // }
    }
  }
});

