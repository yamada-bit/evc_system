let isSubmit = false;
function check(btn) {
    if (isSubmit) {
      show_message('処理中です');
      return false;
    } else {
      let editpos = get_pos().trim();
      if (0 < editpos.length) {
        if(btn != null && $('#othersareas').length){
            let others = $('#othersareas').val();
            if (others == 'nonset') {
                show_message('領域が指定されていないページがあります。');
                return false;
            }
        }
      } else {
        if ($('#othersareas').length) {
            show_message('領域が指定されていません。');
            return false;
        }
      }
      isSubmit = true;
      document.getElementById( 'id_postext' ).value = editpos;
      if (btn != null) {
          btn.value = '処理中';
      }
      return true;
    }
};

// function cancel(){
//     // window.location.href = "{% url 'Evc_App:evidence_list' %}";
//     // history.back();
//     // open( 'FE_Evilist.html', '_blank') ;
//     // location.replace("{% url 'Evc_App:evidence_list' %}");
//     document.getElementById( 'submit_action1' ).value = 'cancel';
//     $('#uploadform').submit();
// }

let pos = [];
let offset_x = 0;
let offset_y = 0;
// window.onload = function()
// {
    const canvas = document.getElementById('area_canvas');
    // 2次元の描画を行うメソッド
    const ctx = canvas.getContext('2d');
    // canvas.width = document.documentElement.clientWidth * 0.9;
    // canvas.height = document.documentElement.clientHeight * 0.9;
    // canvas.style.border = '1px solid';
    // let img = new Image()
    // img.src = '/EvcDataRoot/owner3_root/upload/img/領収書test.jpg'
    // img.onload = function()
    // {
    //     ctx.drawImage(img, 0, 0)
    // }
    let x1 = 0;
    let y1 = 0;
    let x2 = 0;
    let y2 = 0;
    let drag = false;
    let img = null;
    let img_w = 0;
    let img_h = 0;
    let img_scale = 1;
    let angle = 0;

    window.onload = function()
    {
        let card = document.getElementById('card_canvas');
        canvas.width = card.clientWidth;
        canvas.height = card.clientHeight;
        img = document.getElementById('bk_img');
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
        let jsontext = $('#areas').val();
        if (1 < jsontext.length) {
            let pos1 = JSON.parse(jsontext);
            for (let p of pos1)
                pos.push(p);
        }
        angle = $('#angle').val();
        if (angle != 0) {
            pos = rotate_pos(pos, angle, img.width, img.height);
        }
        draw();
        // canvas.addEventListener('click', onClick, false);
        
        if (document.getElementById('preview') == null) {  // プレビュー表示は編集しない
            canvas.addEventListener('mousedown', onMouseDown, false);
            canvas.addEventListener('mouseup', onMouseUp, false);
            canvas.addEventListener('mousemove', onMouseMove, false);
        }
    }

    function onMouseDown(e) {
        let rect = e.target.getBoundingClientRect();
        // ブラウザ上でのクリック座標
        let viewX = e.clientX - rect.left;
        let viewY = e.clientY - rect.top;
        // 表示サイズ(clientWidth / clientHeight <- cssのwidthとheightで指定)と
        // キャンバスサイズ(width / height）の比率
        let scale_w =  canvas.clientWidth / canvas.width;
        let scale_h =  canvas.clientHeight / canvas.height;
        // ブラウザ上でのクリック座標をキャンバス上に変換
        let canvas_x = (viewX / scale_w);
        let canvas_y = (viewY / scale_h);
        // 画像上の座標に変換
        x = Math.floor((canvas_x - offset_x) / img_scale);
        y = Math.floor((canvas_y - offset_y) / img_scale);
        if (0 <= x && x <= img.width && 0 <= y && y <= img.height) {
            drag = true;
            x1 = x;
            y1 = y;
        } else {
            drag = false;
        }
    }
    function onMouseUp(e) {
        if (drag) {
            isEdit = true
            let minx = Math.min(x1, x2);
            let miny = Math.min(y1, y2);
            let maxx = Math.max(x1, x2);
            let maxy = Math.max(y1, y2);
            pos.push( { x1: minx, y1: miny, x2: maxx, y2: maxy } );
            drag = false;
        }
    }

    function onMouseMove(e) {
        if (drag) {
            let rect = e.target.getBoundingClientRect();
            let viewX = e.clientX - rect.left;
            let viewY = e.clientY - rect.top;
            let scale_w = canvas.clientWidth / canvas.width;
            let scale_h = canvas.clientHeight / canvas.height;
            let canvas_x = (viewX / scale_w);
            let canvas_y = (viewY / scale_h);
            x2 = Math.floor((canvas_x - offset_x) / img_scale);
            y2 = Math.floor((canvas_y - offset_y) / img_scale);
            if (x2 < 0)
                x2 = 0;
            if (img.width < x2)
                x2 = img.width;
            if (y2 < 0)
                y2 = 0;
            if (img.height < y2)
                y2 = img.height;
            draw_curr();
        }
    }

    function draw_curr() {
        draw();
        let x = Math.min(x1, x2) * img_scale + offset_x;
        let y = Math.min(y1, y2) * img_scale + offset_y;
        let w = Math.abs(x1 - x2) * img_scale;
        let h = Math.abs(y1 - y2) * img_scale;
        // ctx.fillRect(x, y, w, h);
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        ctx.strokeStyle = 'deepskyblue';
        ctx.lineWidth = 2;
        ctx.stroke();
    }
    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, offset_x, offset_y, img_w, img_h)
        ctx.beginPath();
        for(let p of pos){
            let x = p.x1 * img_scale + offset_x;
            let y = p.y1 * img_scale + offset_y;
            let w = (p.x2 - p.x1) * img_scale;
            let h = (p.y2 - p.y1) * img_scale;
            ctx.rect(x, y, w, h);
        }
        ctx.strokeStyle = 'deepskyblue';
        if (document.getElementById('preview') != null) {  // プレビュー表示は編集しない
            ctx.strokeStyle='#FF0000';
        }
        ctx.lineWidth = 3;
        ctx.stroke();
    }

// };

function rotate_pos(pos1, angle, w, h) {
    pos2 = [];
    // var nRadians = angle * 3.14159 / 180;
    // var nSin = Math.sin(nRadians);
    // var nCos = Math.cos(nRadians);
    let x = 0;
    let y = 0;
    if (angle == 0) {
        nSin = 0;
        nCos = 1;
    }
    if (angle == 90) {
        nSin = 1;
        nCos = 0;
        x = w;
    }
    if (angle == 180) {
        nSin = 0;
        nCos = -1;
        x = w;
        y = h;
    }
    if (angle == 270) {
        nSin = -1;
        nCos = 0;
        y = h;
    }
    for (let p of pos1) {
        x1 = nCos * p.x1 - nSin * p.y1 + x;
        y1 = nSin * p.x1 + nCos * p.y1 + y;
        x2 = nCos * p.x2 - nSin * p.y2 + x;
        y2 = nSin * p.x2 + nCos * p.y2 + y;
        let minx = Math.min(x1, x2);
        let miny = Math.min(y1, y2);
        let maxx = Math.max(x1, x2);
        let maxy = Math.max(y1, y2);

        pos2.push( { x1: minx, y1: miny, x2: maxx, y2: maxy } );
    }
    return pos2;
}
function get_rotate_pos(angle) {
    if (angle == -90) {
        x1 = h - symbol.bounding_box.vertices[0].y
        y1 = symbol.bounding_box.vertices[0].x
        x2 = h - symbol.bounding_box.vertices[2].y
        y2 = symbol.bounding_box.vertices[2].x
    } else if (angle == 90) {
        x1 = symbol.bounding_box.vertices[0].y
        y1 = w - symbol.bounding_box.vertices[0].x
        x2 = symbol.bounding_box.vertices[2].y
        y2 = w - symbol.bounding_box.vertices[2].x
    } else if (angle == 180) {
        x1 = w - symbol.bounding_box.vertices[0].x
        y1 = h - symbol.bounding_box.vertices[0].y
        x2 = w - symbol.bounding_box.vertices[2].x
        y2 = h - symbol.bounding_box.vertices[2].y
    } else {
        x1 = symbol.bounding_box.vertices[0].x
        y1 = symbol.bounding_box.vertices[0].y
        x2 = symbol.bounding_box.vertices[2].x
        y2 = symbol.bounding_box.vertices[2].y
    }
    pos += [x1, y1, x2, y2]
    return pos
}
// 領域クリア
function clear_all() {
    pos = [];
    draw();
    isEdit = true
}
// 座標データをサーバに返す
function get_pos() {
    if (pos.length < 1 || img_w == 0 || img_h == 0)
        return '';
    pos.sort((a, b) => {
        return a.y1 < b.y1 ? -1 : 1;
    });
    let posy1 = [];
    let outpos = [];
    posy1 = pos;
    // 矩形をY座標で並べ替える
    // 矩形の半分より上か下かで分割
    // 最大5分割
    for (let i = 0; i < 5; i++){
        posy1 = sort_y(posy1, outpos)
        if (posy1.length == 0) {
            break;
        }
    }
    // 最終エリアをx座標でソート
    if (0 < posy1.length) {
        posy1.sort((a, b) => {
            return a.x1 < b.x1 ? -1 : 1;
        });
        for (let p of posy1) {
            outpos.push(p);
        }
    }
    if (angle != 0) {
        outpos = rotate_pos(outpos, 360 - angle, img.height, img.width);
    }
    // JSONデータで返す
    let json_text = JSON.stringify(outpos);
    return json_text;
}
function sort_y(pos0, pos1){
    idx = 0;
    posy1 = [];
    posy2 = [];
    for (let p of pos0) {
        if (idx== 0) {
            pre_y = (p.y2 + p.y1) / 2;
            posy1.push(p);
        } else {
            if (pre_y < p.y1)
                posy2.push(p);
            else
                posy1.push(p);
        }
        idx++;
    }
    // エリアをx座標でソート
    posy1.sort((a, b) => {
        return a.x1 < b.x1 ? -1 : 1;
    });
    for (let p of posy1)
        pos1.push(p);
    return posy2;
}