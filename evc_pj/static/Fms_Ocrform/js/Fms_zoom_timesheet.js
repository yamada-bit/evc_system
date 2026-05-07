if (document.getElementById('edit')) {
  document.getElementById('edit').addEventListener('click', edit);
}
if (document.getElementById('update')) {
  document.getElementById('update').addEventListener('click', update);
}
document.getElementById('cancel').addEventListener('click', cancel);
document.getElementById('delete_data').addEventListener('click', delete_data);
// document.getElementById('delete_evidence').addEventListener('click', click_delete);
// document.getElementById('id_category').addEventListener('change', function() {changeColor_w(this);});
// const $dialog_partner = document.getElementById('detect_partner');

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
function update(){
//////////////////しおりを更新する///////////////////////////
  var result = $('#shiori_text').prop('disabled');
  if(!result) {
    // text = document.getElementById( 'shiori_text' ).value;
    // document.getElementById( 'id_fulltext' ).value = text;
    $('#form1').submit();
  }
}
function edit(){
///////////////しおりを編集可能にする//////////////////////
// document.getElementById( 'shiori_text' ).disabled = false;
  var result = $('#shiori_text').prop('disabled');
  if(result) {
    $('#shiori_text').prop('disabled', false);
  }
  else {
    $('#shiori_text').prop('disabled', true);
  }      
}
function commit(){
////////////////検索条件をDBに登録/////////////////////////
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  $('#form2').submit();
}
var isSubmit = false;
function click_delete(){
  if (isSubmit) {
    return;
  }
  $modal.showModal();
}
function delete_data(){
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  document.getElementById( 'submit_action2' ).value = 'delete';
  $('#form2').submit();
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
    // function dialog_close() {
    //   $dialog_partner.close();     
    // }
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
