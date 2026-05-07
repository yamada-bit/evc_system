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
// canvas.style.border = "1px solid";
// let img = new Image()
// img.src = '/EvcData/test.jpg'
// img.onload = function()
// {
//     ctx.drawImage(img, 0, 0)
// }
let lpx1 = 0;
let lpy1 = 0;
let lpx2 = 0;
let lpy2 = 0;
let drag = false;
let ocrform_img = null;
let img_w = 0;
let img_h = 0;
let img_scale = 1;
let angle = 0;
let zoom_base = 256;
let zoom_scale = 1;
let offset_x = 0;
let offset_y = 0;
let area_no_max = 0;

let selected_all = false;
let select_areas = [];
let handle = 0;
const handle_size = 8;
let dialog_table = document.getElementById('dialog_table');
let add_table = false;
let table_row = 1;
let table_names = [];
let table_cols = [];
let act_mode = 1;   // 1:枠入力 2:枠選択

window.onload = function() {
    ocrform_img = document.getElementById('bk_img');
    // canvas.width = img.width;
    // canvas.height = img.height;
    if (0 < ocrform_img.width && 0 < ocrform_img.height) {
        img_scale = Math.min(canvas.width / ocrform_img.width, canvas.height / ocrform_img.height);
    }
    if (img_scale == 0) {
        img_scale = 1;
    }
    // 画像の表示サイズ
    img_w = Math.floor(ocrform_img.width * img_scale);
    img_h = Math.floor(ocrform_img.height * img_scale);
    // if (img_w < canvas.width)
    //     offset_x = (canvas.width - img_w) / 2;
    // offset_x = 10;
    // ctx.drawImage(ocrform_img, offset_x, offset_y, img_w, img_h);
    let jsontext = $('#areas').val();
    if (1 < jsontext.length) {
        let areas1 = JSON.parse(jsontext);
        for (let p of areas1) {
            if  (area_no_max < Number(p.text)) {
                area_no_max = Number(p.text);
            }
            areas.push(p);
        }
    }        
    // angle = $('#angle').val();
    // if (angle != 0) {
    //     areas = rotate_pos(areas, angle, ocrform_img.width, ocrform_img.height);
    // }
    canvas.addEventListener('mousedown', onMouseDown, false);
    canvas.addEventListener('mouseup', onMouseUp, false);
    canvas.addEventListener('mousemove', onMouseMove, false);
    draw();
    initTable();
}
// 拡大・縮小
function zoom(zoom) {
    if (zoom == -1) {
        if (16 < zoom_base) {
            zoom_base /= 2;
            canvas.width /= 2;
            canvas.height /= 2;
            zoom_scale = zoom_base / 256;
        }
    } else {
        if (zoom_base < 4096) {
            zoom_base *= 2;
            canvas.width *= 2;
            canvas.height *= 2;
            zoom_scale = zoom_base / 256;
        }
    }
    draw();
}

function onMouseDown(e) {
    let rect = e.target.getBoundingClientRect();
    // ブラウザ上でのクリック座標
    let viewX = e.clientX - rect.left;
    let viewY = e.clientY - rect.top;
    // 画像上の座標に変換
    let [x, y] = dp2LP(viewX, viewY);
    handle = -1;
    if (0 <= x && x <= ocrform_img.width && 0 <= y && y <= ocrform_img.height) {
        drag = true;
        lpx1 = lpx2 = x;
        lpy1 = lpy2 = y;
        if (!add_table) {
            selectHandle();
        }
        var elem = document.getElementById('add_mode');
        if (elem.checked){
            act_mode = 1;
        } else {
            act_mode = 2;
        }        
    } else {
        drag = false;
    }
}
function onMouseUp(e) {
    if (drag) {
        drag = false;
        isEdit = true;
        let size_min = 4;   // 入力領域の最小サイズ
        if (0 < handle) {
            let selectIdx = select_areas[0];
            let p = areas[selectIdx];
            if (size_min < Math.abs(p.x1 - p.x2) && size_min < Math.abs(p.y1 - p.y2)) {
                let minx = Math.min(p.x1, p.x2);
                let miny = Math.min(p.y1, p.y2);
                let maxx = Math.max(p.x1, p.x2);
                let maxy = Math.max(p.y1, p.y2);
                p.x1 = minx;
                p.y1 = miny;
                p.x2 = maxx;
                p.y2 = maxy;
            }
            handle = -1;
            return;
        }
        if (size_min < Math.abs(lpx1 - lpx2) && size_min < Math.abs(lpy1 - lpy2)) {
            let minx = Math.min(lpx1, lpx2);
            let miny = Math.min(lpy1, lpy2);
            let maxx = Math.max(lpx1, lpx2);
            let maxy = Math.max(lpy1, lpy2);
            if (act_mode == 2) {
                selectRect(minx, miny, maxx, maxy);
                draw();
                return;
            }
            let text = String(area_no_max + 1);
            areas.push( { x1: minx, y1: miny, x2: maxx, y2: maxy, text:text } );
            area_no_max++;
            select_areas = []
            select_areas.push(areas.length - 1);
            // if (add_table) {
            //     // table_obj.push(areas.length - 1);
            //     addTableItem(minx, miny, maxx, maxy);
            // }
            draw();
        } else {
            selectAreas();
            draw();
        }
    }
    add_table = false;
}
function onMouseMove(e) {
    let rect = e.target.getBoundingClientRect();
    let viewX = e.clientX - rect.left;
    let viewY = e.clientY - rect.top;
    if (drag) {
        [lpx2, lpy2] = dp2LP(viewX, viewY);
        if (lpx2 < 0)
            lpx2 = 0;
        if (ocrform_img.width < lpx2)
            lpx2 = ocrform_img.width;
        if (lpy2 < 0)
            lpy2 = 0;
        if (ocrform_img.height < lpy2)
            lpy2 = ocrform_img.height;
        draw();
        draw_curr();
    } else {
        let [x, y] = dp2LP(viewX, viewY);
        over = overtHandle(x, y);
        if (over == 5) {
            document.body.style.cursor = "move";        // 移動
        } else if (over == 1) {
            document.body.style.cursor = "nw-resize";   // 左上
        } else if (over == 2) {
            document.body.style.cursor = "ne-resize";   // 右上
        } else if (over == 3) {
            document.body.style.cursor = "se-resize";   // 右下
        } else if (over == 4) {
            document.body.style.cursor = "sw-resize";   // 左下
        } else {
            document.body.style.cursor = "default";
        }
    }
}
function dp2LP(viewX, viewY) {
    // 表示サイズ(clientWidth / clientHeight <- cssのwidthとheightで指定)と
    // キャンバスサイズ(width / height）の比率
    let scale_w =  canvas.clientWidth / canvas.width;
    let scale_h =  canvas.clientHeight / canvas.height;
    // ブラウザ上でのクリック座標をキャンバス上に変換
    let canvas_x = (viewX / scale_w);
    let canvas_y = (viewY / scale_h);
    // 画像上の座標に変換
    let x = Math.floor((canvas_x - offset_x) / img_scale / zoom_scale);
    let y = Math.floor((canvas_y - offset_y) / img_scale / zoom_scale);
    return [x, y];
}
function lp2DP(lx, ly) {
    let x = Math.floor(lx * img_scale * zoom_scale) + offset_x;
    let y = Math.floor(ly * img_scale * zoom_scale) + offset_y;
    return [x, y];
}
function draw_curr() {
    let x = Math.min(lpx1, lpx2);
    let y = Math.min(lpy1, lpy2);
    [x, y] = lp2DP(x, y);
    let w = Math.abs(lpx1 - lpx2);
    let h = Math.abs(lpy1 - lpy2);
    [w, h] = lp2DP(w, h);
    // ctx.fillRect(x, y, w, h);
    if (0 < handle) {
    } else if (add_table) {
        drawTable(x, y, w, h);
    } else {
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        ctx.strokeStyle = 'deepskyblue';
        ctx.lineWidth = 2;
        ctx.stroke();
    }
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(ocrform_img, offset_x * zoom_scale, offset_y * zoom_scale, img_w * zoom_scale, img_h * zoom_scale)

    // ctx.font =  'bold ' + String(40 * img_scale * zoom_scale) + "px 'ＭＳ ゴシック'";
    ctx.font = String(40 * img_scale * zoom_scale) + "px 'ＭＳ ゴシック'";
    ctx.fillStyle = "red";
    ctx.textBaseline = "top";
    for (const [idx, p] of areas.entries()) {
        if (0 < handle) {
            let selectIdx = select_areas[0];
            if (idx == selectIdx) {
                if (handle == 1) {
                    p.x1 = lpx2;
                    p.y1 = lpy2;
                } else if (handle == 2) {
                    p.x2 = lpx2;
                    p.y1 = lpy2;
                } else if (handle == 3) {
                    p.x2 = lpx2;
                    p.y2 = lpy2;
                } else if (handle == 4) {
                    p.x1 = lpx2;
                    p.y2 = lpy2;
                }
            }
        }
        let [x, y] = lp2DP(p.x1, p.y1);
        let [w, h] = lp2DP(p.x2 - p.x1, p.y2 - p.y1);
        let find = select_areas.indexOf(idx);
        if (find == -1) {   // 未選択の図形を描画
            // if (idx % 2 == 0) {
            //     ctx.strokeStyle = "red";
            //     ctx.lineWidth = 1;
            // } else {
            //     ctx.strokeStyle = "blue";
            //     ctx.lineWidth = 1;
            // }
            ctx.beginPath();
            ctx.strokeStyle = "red";
            ctx.lineWidth = 2;
            ctx.rect(x, y, w, h);
            ctx.stroke();
            // drawAreaNo(x, y, p.text);
        }
        // let findtable = table_obj.indexOf(idx);
        // if (findtable != -1) {
        //     drawTable(x, y, w, h);
            // if (find != -1) {
            //     drawAreaNo(x, y, p.text);
            // }
        // }
        drawAreaNo(x, y, p.text);
    }
    // 選択図形描画
    // ctx.strokeStyle = 'deepskyblue';
    // ctx.strokeStyle="#FF0000";
    // ctx.lineWidth = 3;
    // ctx.stroke();
    ctx.beginPath();
    for (let idx of select_areas) {
        let p = areas[idx];
        let [x, y] = lp2DP(p.x1, p.y1);
        let [w, h] = lp2DP(p.x2 - p.x1, p.y2 - p.y1);
        ctx.rect(x, y, w, h);
    }
    // ctx.strokeStyle="#FF00FF";
    ctx.strokeStyle = "#0000FF";
    ctx.lineWidth = 3;
    ctx.stroke();
    // Handle(4点)の描画
    if (select_areas.length == 1) {
        let area = handle_size;
        let idx = select_areas[0];
        let p = areas[idx];
        let [x, y] = lp2DP(p.x1, p.y1);
        let [w, h] = lp2DP(p.x2 - p.x1, p.y2 - p.y1);
        let startx = x - area;
        let starty = y - area;
        let endx = (x + w) - area;
        let endy = (y + h) - area;
        ctx.beginPath();
        ctx.rect(startx, starty, 2 * area, 2 * area);
        ctx.rect(endx, starty, 2 * area, 2 * area);
        ctx.rect(endx, endy, 2 * area, 2 * area);
        ctx.rect(startx, endy, 2 * area, 2 * area);
        ctx.strokeStyle = "#0000FF";
        ctx.lineWidth = 1;
        ctx.stroke();
    }
}
function drawAreaNo(x, y, text) {
    let txw = ctx.measureText(text);
    let textwidth = txw.width - 4;
    let textheight = txw.actualBoundingBoxAscent + txw.actualBoundingBoxDescent - 4;
    ctx.beginPath();
    ctx.fillStyle = 'white';
    ctx.fillRect(x + 2, y + 2, textwidth, textheight);
    ctx.fillStyle = 'red';
    ctx.fillText(text, x, y);
}

function drawTable(x, y, w, h) {
    let startx = x;
    let starty = y;
    let endx = startx + w;
    let endy = starty + h;
    if (table_row < 1) {
        table_row = 1;
    }
    let div_w = w;
    let div_h = h / table_row;
    ctx.beginPath();
    ctx.strokeStyle = 'green';
    for (let i = 1; i < table_row; i++) {
        ctx.moveTo(startx, starty + div_h * i);
        ctx.lineTo(endx, starty + div_h * i);
    }
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.beginPath();
    ctx.rect(x, y, w, h);
    if (add_table) {
        ctx.strokeStyle = 'deepskyblue';
    } else {
        ctx.strokeStyle = 'red';
    }
    ctx.lineWidth = 2;
    ctx.stroke();

}
function addTableItem(table_name, table_json, item_name, item_json) {
    if (select_areas.length != 1) {
        return;
    }
    let selectIdx = select_areas[0];
    let p = areas[selectIdx];
    if (table_row < 1) {
        table_row = 1;
    }
    let startx = p.x1;
    let starty = p.y1;
    let endx = p.x2;
    let endy = p.y2;
    let div_w = (endx - startx);
    let div_h = (endy - starty) / table_row;

    if (1 < div_w && 1 < div_h) {
        let result = table_names.includes(table_json);
        if (!result) {
            table_names.push(table_json);
            addItem(table_name, table_json, table_json, '');
            // addItem(table_name, table_json, table_json + '__0__0', '');
            // json名に '_'が含まれるため区別できるように'__'
        }
        let exist = getLastCol(table_json); // 表に列が登録されているか
        let margin = 2;
        for (let i = 0; i < table_row; i++) {
            let minx = startx + margin;
            let miny = starty + div_h * i + margin;
            let maxx = endx - margin;
            let maxy = starty + div_h * (i + 1) - margin;
            let text = String(area_no_max + 1);
            let add_item_name = item_name + '_' + String(i + 1);
            let add_table_id = table_json;  // + '__' + String(i + 1) + '__' + item_json;
            // json名に '_'が含まれるため区別できるように'__'
            areas.push( { x1: minx, y1: miny, x2: maxx, y2: maxy, text:text } );
            area_no_max++;
            if (exist) {
                insertItem(add_item_name, item_json, add_table_id, text, i);
            } else {
                addItem(add_item_name, item_json, add_table_id, text);
            }
        }
        clearAreas();
    }
}
function selectAreas() {
    let selectIdx = -1;
    let len = areas.length;
    for (let i = len - 1; 0 <= i; i--) {
        let p = areas[i];
        if (p.x1 < lpx1 && lpx2 < p.x2 && p.y1 < lpy1 && lpy2 < p.y2) {
            selectIdx = i;
            break;
        }
    }
    if (selectIdx == -1) {
        return;
    }
    if (0 < select_areas.length) {
        let idx = select_areas.indexOf(selectIdx);
        if (idx != -1) {
            select_areas.splice(idx, 1);
        } else {
            select_areas.push(selectIdx);
        }
    } else {
        select_areas.push(selectIdx);
    }
}
function selectRect(minx, miny, maxx, maxy) {
    let len = areas.length;
    for (let i = len - 1; 0 <= i; i--) {
        let p = areas[i];
        if (minx < p.x1 && p.x2 < maxx && miny < p.y1 && p.y2 < maxy) {
            select_areas.push(i);
        }
    }
}
function clearAreas() {
    if (0 < select_areas.length) {
        select_areas.sort((a, b) => b - a);
        for (let idx of select_areas) {            
            areas.splice(idx, 1);
            // let find = table_obj.indexOf(idx);
            // if (find != -1) {
            //     table_obj.splice(find, 1);
            // } else {
            //     for (const [tidx, t] of table_obj.entries()) {
            //         if (idx < t) {
            //             table_obj[tidx] = t - 1;
            //         }
            //     }
            // }
        }
        select_areas = [];
        draw();
    }
}
function actMode(btn) {
    if (act_mode == 1) {
        btn.textContent  = '枠選択';
        act_mode = 2;
    } else {
        btn.textContent  = '枠入力';
        act_mode = 1;
    } 
}

function selectAll(btn) {
    select_areas = [];
    if (!selected_all) {
        let len = areas.length;
        for (let i = len - 1; 0 <= i; i--) {
            select_areas.push(i);
        }
        btn.textContent  = '選択解除';
    } else {
        btn.textContent  = '全選択';
    } 
    selected_all = !selected_all;
    draw();
}
function selectHandle() {
    handle = -1;
    if (select_areas.length != 1) {
        return;
    }
    let selectIdx = select_areas[0];
    let len = areas.length;
    let [area, dmy] = dp2LP(handle_size, 1);  // 5px * 2 の領域で選択判定
    let p = areas[selectIdx];
    if (p.x1 - area < lpx1 && lpx1 < p.x1 + area && p.y1 - area < lpy1 && lpy1 < p.y1 + area) {
        handle = 1;
    } else if (p.x2 - area < lpx1 && lpx1 < p.x2 + area && p.y1 - area < lpy1 && lpy1 < p.y1 + area) {
        handle = 2;
    } else if (p.x2 - area < lpx1 && lpx1 < p.x2 + area && p.y2 - area < lpy1 && lpy1 < p.y2 + area) {
        handle = 3;
    } else if (p.x1 - area < lpx1 && lpx1 < p.x1 + area && p.y2 - area < lpy1 && lpy1 < p.y2 + area) {
        handle = 4;
    }
    // handle = -1;
}
function overtHandle(lpx1, lpy1) {
    if (select_areas.length != 1) {
        return 0;
    }
    let over = 0;
    let selectIdx = select_areas[0];
    let [area, dmy] = dp2LP(handle_size, 1);  // 5px * 2 の領域で選択判定
    let p = areas[selectIdx];
    if (p.x1 - area < lpx1 && lpx1 < p.x1 + area && p.y1 - area < lpy1 && lpy1 < p.y1 + area) {
        over = 1;
    } else if (p.x2 - area < lpx1 && lpx1 < p.x2 + area && p.y1 - area < lpy1 && lpy1 < p.y1 + area) {
        over = 2;
    } else if (p.x2 - area < lpx1 && lpx1 < p.x2 + area && p.y2 - area < lpy1 && lpy1 < p.y2 + area) {
        over = 3;
    } else if (p.x1 - area < lpx1 && lpx1 < p.x1 + area && p.y2 - area < lpy1 && lpy1 < p.y2 + area) {
        over = 4;
    }
    return over;
}
// 表追加
function addTable() {
    if (select_areas.length != 1) {
        show_message('テーブルを配置する領域が選択されていません。');
        return;
    }
    dialog_table.showModal();
}
// 全角数値を半角に
function conv_num(input_num) {
    let str = input_num.replace(/[０-９]/g, function(s) {
        return String.fromCharCode(s.charCodeAt(0) - 65248);
    });
    return str;
}

function dialog_table_ok() {
    let input_row = document.getElementById( "table_row" ).value;
    let row_str = conv_num(input_row);
    table_row = Number(row_str);
    let table_name = document.getElementById( "table_name" ).value.trim();
    // let table_no = document.getElementById( "table_no" ).value;
    // let col_no = document.getElementById( "col_no" ).value;
    let table_json = document.getElementById( "table_json" ).value.trim();
    let item_name = document.getElementById( "item_name" ).value.trim();
    let item_json = document.getElementById( "item_json" ).value.trim();
    // add_table = true;
    // $('#table_row').val(1);
    // $('#table_name').val('');
    // // $('#table_no').val(1);
    // // $('#col_no').val(1);
    // $('#item_name').val('');
    // $('#item_json').val('');
    // $('#table_json').val('');
    dialog_table.close();
    addTableItem(table_name, table_json, item_name, item_json);
}
function dialog_table_close() {
//   add_table = false;
  dialog_table.close();
}
