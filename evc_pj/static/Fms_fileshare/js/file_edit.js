document.getElementById('update').addEventListener('click', update);
document.getElementById('cancel').addEventListener('click', cancel);
document.getElementById('delete_file').addEventListener('click', click_delete);

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
      delete_file();
  });
}
////////////////検索条件をDBに登録/////////////////////////
function commit(){
    if (isSubmit) {
      return;
    }
    isSubmit = true;
    $('#form2').submit();
  }
 
function update() {
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  document.getElementById( 'submit_action2' ).value = 'update';

  $('#form2').submit();
}
function click_delete(){
  if (isSubmit) {
    return;
  }
  $modal.showModal();
}
function delete_file(){
  if (isSubmit) {
    return;
  }
  isSubmit = true;
  document.getElementById( 'submit_action2' ).value = 'delete';
  $('#form2').submit();
}

function cancel(){
  // window.location.href = "{% url 'Fms_Ocrform:entry_list' %}";
  // history.back();
  // open( 'FE_Entrylist.html', '_blank') ;
  // location.replace("{% url 'Fms_Ocrform:entry_list' %}");

  if (isSubmit) {
    show_message('処理中です');
    return;
  }
  document.getElementById( 'submit_action2' ).value = 'cancel';
  $('#form2').submit();
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
      location.href = href;
    }
  }
});

/* PDF.js または　マウスホイールでズーム、ドラッグでスクロールを使う場合はコメント --> 
let offset_x = 0;
let offset_y = 0;
// window.onload = function() {
let img = null;
let img_w = 0;
let img_h = 0;
let img_scale = 1;
let angle = 0;
let zoom_scale = 256;
const canvas = document.getElementById('image_canvas');
// 2次元の描画を行うメソッド
const ctx = canvas.getContext('2d');
// canvas.width = document.documentElement.clientWidth * 0.9;
// canvas.height = document.documentElement.clientHeight * 0.9;
let imagebox = document.getElementById('imagebox');
canvas.width = imagebox.clientWidth * 0.9;
canvas.height = imagebox.clientHeight * 0.9;

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
<--- */

/* マウスホイールでズーム、ドラッグでスクロール */
/* スマホ対応のために、ピンチイン・アウト（ズーム） と ドラッグ（パン） をタッチ操作で実装 */
const canvas = document.getElementById("image_canvas");
const ctx = canvas.getContext("2d");

let imagebox = document.getElementById('imagebox');
canvas.width = imagebox.clientWidth;
canvas.height = imagebox.clientHeight;

let scale = 1;  // 拡大縮小率
let offsetX = 0, offsetY = 0; // 移動オフセット
let lastX, lastY;
let dragging = false;
let lastDistance = null; // ピンチ操作用

// let img1 = document.getElementById('bk_img1').value;
// let img2 = document.getElementById('bk_img2').value;
// const images = [img1, img2];
let page_max = document.getElementById('page_count').value;
let currentIndex = 0; // 現在の画像インデックス
let img = new Image();
let init = true;

function get_image_url(index) {
  let imgurl = document.getElementById('bk_img').value;
  const paddedIndex = (index + 1).toString().padStart(3, '0');
  const startIndex = imgurl.lastIndexOf('_') + 1;
  const endIndex = imgurl.lastIndexOf('.');
  let filepath = imgurl.substr(0, startIndex) + paddedIndex + imgurl.substr(endIndex)
  return filepath
}
function loadImage(index) {
  img.src = get_image_url(index);
  img.onload = () => {
    if (init) {
      if (0 < img.width && 0 < img.height)
        scale = Math.min(canvas.width / img.width, canvas.height / img.height);
      if (scale === 0)
        scale = 1;
      if (img.width*scale < canvas.width)
        offsetX = (canvas.width - img.width*scale) / 2;
      init = false;
    };
    draw();
  };
}
// ボタンクリックで画像切り替え
document.getElementById("prev_page").addEventListener("click", () => {
//  最初まで行ったら最後に戻る
//  currentIndex = (currentIndex - 1 + images.length) % images.length;
// loadImage(currentIndex);
  if (0 < currentIndex) {
    currentIndex = currentIndex - 1
    loadImage(currentIndex);
    if (currentIndex == 0) {
      document.getElementById("btn_prev").classList.add('disabled');
    }
    if (currentIndex == page_max - 2) {
      document.getElementById("btn_next").classList.remove('disabled');
    }
  }
});

document.getElementById("next_page").addEventListener("click", () => {
  // 最後まで行ったら最初に戻る
  // currentIndex = (currentIndex + 1) % images.length;
  // loadImage(currentIndex);
  if (currentIndex < page_max - 1) {
    currentIndex = currentIndex + 1
    loadImage(currentIndex);
    if (currentIndex == page_max - 1) {
      document.getElementById("btn_next").classList.add('disabled');
    }
    if (currentIndex == 1) {
      document.getElementById("btn_prev").classList.remove('disabled');
    }
  }
});

// 最初の画像を表示
loadImage(currentIndex);

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);
    ctx.restore();
}
// ズーム処理
// ホイールでズーム
canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    const zoomFactor = 1.1;
    const mouseX = event.offsetX;
    const mouseY = event.offsetY;
    
    const scaleFactor = event.deltaY < 0 ? zoomFactor : 1 / zoomFactor;

    // マウス位置を基準に拡大縮小
    offsetX = mouseX - (mouseX - offsetX) * scaleFactor;
    offsetY = mouseY - (mouseY - offsetY) * scaleFactor;
    scale *= scaleFactor;
    
    draw();
});

// ドラッグ移動 (パン)
// マウスによるパン (スクロール)
canvas.addEventListener("mousedown", (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.style.cursor = "grabbing";
});
canvas.addEventListener("mousemove", (event) => {
    if (!dragging) return;
    offsetX += event.clientX - lastX;
    offsetY += event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    draw();
});
canvas.addEventListener("mouseup", () => {
    dragging = false;
    canvas.style.cursor = "grab";
});

canvas.addEventListener("mouseleave", () => {
    dragging = false;
    canvas.style.cursor = "grab";
});
// タッチによるパン (スクロール)
canvas.addEventListener("touchstart", (event) => {
  if (event.touches.length === 1) { // 1本指ドラッグ
      dragging = true;
      lastX = event.touches[0].clientX;
      lastY = event.touches[0].clientY;
  }
  if (event.touches.length === 2) { // 2本指でピンチ開始
      lastDistance = getDistance(event.touches);
  }
});

canvas.addEventListener("touchmove", (event) => {
  event.preventDefault(); // デフォルトのスクロールを無効化

  if (event.touches.length === 1 && dragging) { // 1本指ドラッグ
      offsetX += event.touches[0].clientX - lastX;
      offsetY += event.touches[0].clientY - lastY;
      lastX = event.touches[0].clientX;
      lastY = event.touches[0].clientY;
      draw();
  }

  if (event.touches.length === 2) { // 2本指ピンチイン・アウト
      const newDistance = getDistance(event.touches);
      const scaleFactor = newDistance / lastDistance;
      lastDistance = newDistance;

      // ズームの最大・最小制限
      scale *= scaleFactor;
      scale = Math.max(0.5, Math.min(3, scale));

      draw();
  }
});
canvas.addEventListener("touchend", () => {
  dragging = false;
  lastDistance = null;
});
// 2本指の距離を計算
function getDistance(touches) {
  const dx = touches[0].clientX - touches[1].clientX;
  const dy = touches[0].clientY - touches[1].clientY;
  return Math.sqrt(dx * dx + dy * dy);
}

/* PDF.jsを使う場合 --> 
ver４以降表示されない　pdfjsLib not definedになる
// PDF.jsの設定
const url = document.getElementById( 'pdf_url' ).value;
let pdf = null;
let currentPage = 1;
let scale = 1.0;  // 初期スケール（拡大縮小の割合）

// PDFのロードとレンダリング
const loadingTask = pdfjsLib.getDocument(url);
loadingTask.promise.then(function(pdfDoc) {
    pdf = pdfDoc;
    renderPage(currentPage);
}).catch(function(error) {
    console.error('Error loading PDF: ' + error);
});

// ページをレンダリングする関数
function renderPage(pageNum) {
    pdf.getPage(pageNum).then(function(page) {
        const canvas = document.getElementById('pdf-canvas');
        const context = canvas.getContext('2d');
        const viewport = page.getViewport({ scale: scale });
        
        // キャンバスのサイズを設定
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        
        // PDFページを描画
        page.render({
            canvasContext: context,
            viewport: viewport
        }).promise.then(function() {
            console.log('Page rendered');
        });
    });
}

// ズームインのボタン
document.getElementById('zoom-in').addEventListener('click', function() {
    scale += 0.1;  // ズームイン（10%ずつ拡大）
    renderPage(currentPage);  // 再描画
});

// ズームアウトのボタン
document.getElementById('zoom-out').addEventListener('click', function() {
    if (scale > 0.2) {  // 最小スケールを0.2に設定
        scale -= 0.1;  // ズームアウト（10%ずつ縮小）
        renderPage(currentPage);  // 再描画
    }
});
// 次のページ
document.getElementById('next-page').addEventListener('click', function() {
    if (currentPage < pdf.numPages) {
        currentPage++;
        renderPage(currentPage);
    }
});

// 前のページ
document.getElementById('prev-page').addEventListener('click', function() {
    if (currentPage > 1) {
        currentPage--;
        renderPage(currentPage);
    }
});
  <---  */
