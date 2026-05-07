// document.getElementById('edit').addEventListener('click', edit);
// document.getElementById('update').addEventListener('click', update);
document.getElementById('cancel').addEventListener('click', cancel);
// document.getElementById('delete_evidence').addEventListener('click', delete_evidence);
// document.getElementById('delete_evidence').addEventListener('click', click_delete);
// document.getElementById('id_category').addEventListener('change', function() {changeColor_w(this);});

/** 
* 処理を適用するテキストボックスへのイベント設定
* onBlur : カンマ削除処理実施
*/
// var elm = document.getElementById('id_amount');
// elm.addEventListener('blur', function(){ this.value = delFigure(this.value) }, false);
// elm.addEventListener('blur', function(){ this.value = numtolocale(this.value) }, false);
/**
* カンマ外し
* 入力値のカンマを取り除いて返却
* [引数]   strVal: 半角でカンマ区切りされた数値
* [返却値] String(): カンマを削除した数値
*/
// function delFigure(strVal){
//   return strVal.replace( /,/g , '' );
// }
// 3桁のカンマ区切りにする
// function numtolocale(strVal){
//   try {
//     numstr = strVal.replace( /,/g , '' );
//     str = Number(numstr).toLocaleString();
//   } catch (e) {
//     return strVal;
//   }
//   return str;
// }
function download(){
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
function cancel(){
  // window.location.href = "{% url 'Evc_App:evidence_list' %}";
  // history.back();
  // open( 'FE_Evilist.html', '_blank') ;
  // location.replace("{% url 'Evc_App:evidence_list' %}");
  document.getElementById( 'submit_action2' ).value = 'cancel';
  $('#form2').submit();
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

    window.onload = function()
    {
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
        draw();
    }
    function draw() {
        box = document.getElementById('imagebox');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, offset_x * zoom_scale / 256, offset_y * zoom_scale / 256, img_w * zoom_scale / 256, img_h * zoom_scale / 256)
		box.scrollTo(offset_x * zoom_scale / 256, offset_y * zoom_scale / 256);		
    }
    function drawRotatedImage(img, x, y, angle) {
        context.save();
        context.translate(x, y);
        context.rotate(angle * Math.PI / 180);
        context.drawImage(img, -(img.width/2), -(img.height/2));
        context.restore();
    }
    function setResize(zoom) {
      if (zoom == -1) {
        if (16 < zoom_scale) {
          zoom_scale /= 2;
          canvas.width /= 2;
          canvas.height /= 2;
        }
      } else {
        if (zoom_scale < 4096) {
          zoom_scale *= 2;
          canvas.width *= 2;
          canvas.height *= 2;
        }
      }
      draw();
    }
  const openButtons = document.querySelectorAll('.showModal');
  const closeButton = document.getElementById('closeModal');

  const modal = document.querySelector('.history-dialog');

  const toggleModal = () => {
    if (!modal) return;
  
    const form = document.querySelector('.modal');
  
    openButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        modal.showModal();
      });
    });
  
    closeButton.addEventListener('click', () => {
        modal.close();
    });
  };
  toggleModal();