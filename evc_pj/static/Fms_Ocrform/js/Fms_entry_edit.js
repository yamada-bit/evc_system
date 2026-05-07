document.getElementById('commit').addEventListener('click', commit);
document.getElementById('cancel').addEventListener('click', cancel);
// document.getElementById('delete_entry').addEventListener('click', delete_entry);
document.getElementById('delete_entry').addEventListener('click', click_delete);
document.getElementById('download_file').addEventListener('click', download_file);
// document.getElementById('download_file').addEventListener('click', download);

const $modal = document.getElementById('del-record');
const $closeButton = document.querySelectorAll('#close');
const $scondeleteButton = document.querySelectorAll('#scon_delete');

let isSubmit = false;

for (let i = 0; i < $closeButton.length; i++) {
  $closeButton[i].addEventListener('click', () => {
      $modal.close();
  });
}
for (let i = 0; i < $scondeleteButton.length; i++) {
  $scondeleteButton[i].addEventListener('click', () => {
      $modal.close();
      delete_entry();
  });
}

function commit() {
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  isEdit = false;
  document.getElementById( 'submit_action1' ).value = 'commit';
  document.getElementById( 'object_list_json' ).value = getTableJson();

  $('#form1').submit();
}
function click_delete(){
  if (isSubmit) {
    return;
  }
  $modal.showModal();
}
function delete_entry(){
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  document.getElementById( 'submit_action1' ).value = 'delete';
  $('#form1').submit();
}
function download_file() {
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  document.getElementById( 'object_list_json' ).value = getTableJson();
  document.getElementById( 'submit_action1' ).value = 'download';
  $('#form1').submit();
}

function download(){
  if (isSubmit) {
    show_message('処理中です');
    return;
  }
  if (isEdit) {
    let result = window.confirm('保存が実行されていません。変更内容は破棄されます。\nよろしいですか？');
    if (!result) {
      return;
    }
  }
  let element = document.createElement('a');
  // a要素のhref属性を設定
  let str = $('#export_file').val();
  element.href = str
  // // a要素のdownload属性を設定
  element.download = 'sample.zip';
  // // a要素のtarget属性を設定
  element.target = '_blank';
  // a要素のクリック実行
  element.click();
}

function cancel(){
  // window.location.href = "{% url 'Fms_Ocrform:entry_list' %}";
  // history.back();
  // open( 'FE_Entrylist.html', '_blank') ;
  // location.replace("{% url 'Fms_Ocrform:entry_list' %}");

  if (isEdit) {
    if (isSubmit) {
      show_message('処理中です');
      return;
    }
    let result = window.confirm('保存が実行されていません。変更内容は破棄されます。\nよろしいですか？');
    if (!result) {
      return;
    }
  }
  document.getElementById( 'submit_action1' ).value = 'cancel';
  $('#form1').submit();
}

function getTableJson() {
    let lists = [];
    let idx = 0
    $('table tbody tr').map(function(index, element){
        let item_name = $(element).children().eq(0).children('input').val();
        let item_json = $(element).children().eq(1).children('input').val();
        let item_text = $(element).children().eq(2).children('input').val();
        let area_no = $(element).children().eq(3).children('input').val();
        let table_id = $(element).children().eq(4).children('input').val();
        if (item_name && item_name.trim()) {
            lists[idx] = {
                'item_no': '' + (idx + 1),
                'item_name':item_name,
                'item_json':item_json,
                'item_text':item_text,
                'area_no': area_no,
                'table_id': table_id
            };
            idx++;
        }
    });
    let json_str = JSON.stringify(lists);
    return json_str;
}
let offset_x = 0;
let offset_y = 0;
// window.onload = function()
// {
    const canvas = document.getElementById('image_canvas');
    // 2次元の描画を行うメソッド
    const ctx = canvas.getContext('2d');
    // canvas.width = document.documentElement.clientWidth * 0.9;
    // canvas.height = document.documentElement.clientHeight * 0.9;
    let imagebox = document.getElementById('imagebox');
    canvas.width = imagebox.clientWidth * 0.98;
    canvas.height = imagebox.clientHeight * 0.98;
    // canvas.style.border = '1px solid';
    // let img = new Image()
    // img.src = '/EvcDataRoot/owner3_root/upload/img/領収書test.jpg'
    // img.onload = function()
    // {
    //     ctx.drawImage(img, 0, 0)
    // }
    let img = null;
    let img_w = 0;
    let img_h = 0;
    let img_scale = 1;
    let angle = 0;
  	let zoom_scale = 256;
    let areas = [];
    let isEdit = false;

    window.onload = function() {
        img = document.getElementById('bk_img');
        // canvas.width = img.width;
        // canvas.height = img.height;
        if (0 < img.width && 0 < img.height)
            img_scale = Math.min(canvas.width / img.width, canvas.height / img.height);
        if (img_scale == 0)
            img_scale = 1;
        img_w = img.width * img_scale;
        img_h = img.height * img_scale;
        if (img_w < canvas.width)
            offset_x = (canvas.width - img_w) / 2;
        // offset_x = 10;
        // ctx.drawImage(img, offset_x, offset_y, img_w, img_h);
        angle = $('#angle').val();
        let jsontext = $('#areas').val();
        if (1 < jsontext.length) {
            let areas1 = JSON.parse(jsontext);
            for (let p of areas1) {
                areas.push(p);
            }
        }        
        draw();

        $('.item-list').on('click', function(){
            let area_no = $(this).children().eq(3).children('input').val();
            if (area_no  && area_no.trim()) {
              box = document.getElementById('imagebox');
              const w = box.scrollLeft;
              const h = box.scrollTop;
              draw();
              box.scrollTo(w, h);		
              drawArea(area_no);
          }
        });
        let inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
          input.addEventListener('change', updateValue);
        });        
    }
    function updateValue() {
      isEdit = true;
    }        

    function draw() {
        // box = document.getElementById('imagebox');
        // const w = box.scrollLeft;
        // const h = box.scrollTop;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, offset_x * zoom_scale / 256, offset_y * zoom_scale / 256, img_w * zoom_scale / 256, img_h * zoom_scale / 256)
        // box.scrollTo(offset_x * zoom_scale / 256, offset_y * zoom_scale / 256);		
        // box.scrollTo(w, h);		
    }
    function drawRotatedImage(img, x, y, angle) {
        context.save();
        context.translate(x, y);
        context.rotate(angle * Math.PI / 180);
        context.drawImage(img, -(img.width/2), -(img.height/2));
        context.restore();
    }
    function drawArea(area_no) {
      ctx.font = String(40 * img_scale * zoom_scale / 256) + "px 'ＭＳ ゴシック'";
      ctx.fillStyle = 'red';
      ctx.textBaseline = 'top';
      for (const [idx, p] of areas.entries()) {
        if (p.text == area_no) {
          let [x1, y1] = lp2DP(p.x1, p.y1);
          let [x2, y2] = lp2DP(p.x2, p.y2);
          let [w, h] = [x2 - x1, y2 - y1];
          ctx.beginPath();
          ctx.strokeStyle = 'red';
          ctx.lineWidth = 2;
          ctx.rect(x1, y1, w, h);
          ctx.stroke();
          // drawAreaNo(x, y, p.text);
          break;
        }
      }
    }
    function lp2DP(lx, ly) {
      let x = Math.floor(lx * img_scale * zoom_scale / 256) + offset_x * zoom_scale / 256;
      let y = Math.floor(ly * img_scale * zoom_scale / 256) + offset_y * zoom_scale / 256;
      return [x, y];
    }  
  
    function setResize(zoom) {
      box = document.getElementById('imagebox');
      let w = box.scrollLeft;
      let h = box.scrollTop;
      if (zoom == -1) {
        if (16 < zoom_scale) {
          zoom_scale /= 2;
          canvas.width /= 2;
          canvas.height /= 2;
          w /= 2;
          h /= 2;
        }
      } else {
        if (zoom_scale < 4096) {
          zoom_scale *= 2;
          canvas.width *= 2;
          canvas.height *= 2;
          w *= 2;
          h *= 2;
        }
      }
      box.scrollTo(w, h);		
      draw();
    }

  // document.getElementById('cancel').addEventListener('click', cancel);
  $(document).on('click', 'a', function(e) {
    let id = e.currentTarget.id;
    if (id == 'back_btn' || id == 'next_btn') {
      e.preventDefault();
      let href = $(this).attr('href');
      if (href !== undefined) {
        if (isSubmit) {
          show_message('処理中です');
          return;
        }
        if (isEdit) {
          // let result = window.confirm('保存されていません。ページ移動してよろしいですか？');
          // if (result) {
          //   location.href = href;
          // }
          isSubmit = true;
          document.getElementById( 'object_list_json' ).value = getTableJson();
          document.getElementById( 'submit_action1' ).value = id;
          $('#form1').submit();
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
  