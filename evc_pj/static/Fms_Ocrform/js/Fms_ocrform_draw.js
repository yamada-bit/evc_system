const canvas = document.getElementById('image_canvas');
const ctx = canvas.getContext('2d');
let imagebox = document.getElementById('imagebox');

canvas.width = imagebox.clientWidth * 0.98;
canvas.height = imagebox.clientHeight * 0.98;

let ocrform_img = null;
let img_scale = 1;
let zoom_scale = 1;
let zoom_base = 256;
let offset_x = 0, offset_y = 0;

let lpx1 = 0, lpy1 = 0, lpx2 = 0, lpy2 = 0;
let drag = false;
let area_no_max = 0;

let selected_all = false;
// let areas = [];  // Fms_ocrform_edit.js
let select_areas = [];
let handle = -1;
const handle_size = 8;

let dialog_table = document.getElementById('dialog_table');
let table_row = 1;
let table_names = [];
let table_cols = [];
let act_mode = 1;   // 1:枠入力 2:枠選択 3:移動

// ===== 状態 =====
let isPanning = false;
let moving = false;
let move_start_x = 0;
let move_start_y = 0;
let move_lock_axis = null; // 'x' | 'y' | null

// ===== Undo / Redo =====
let undoStack = [];
let redoStack = [];

let resizing = false;
let resize_handle = -1;
let resize_start_bbox = null;
let resize_start_areas = null;

function saveState() {
    undoStack.push(JSON.stringify({
        areas,
        select_areas,
        zoom_scale,
        zoom_base,
        offset_x,
        offset_y
    }));
    redoStack = [];
}

function undo() {
    if (!undoStack.length) return;
    redoStack.push(JSON.stringify({ areas, select_areas, zoom_scale, offset_x, offset_y }));
    let s = JSON.parse(undoStack.pop());
    areas = s.areas;
    select_areas = s.select_areas;
    zoom_scale = s.zoom_scale;
    offset_x = s.offset_x;
    offset_y = s.offset_y;
    draw();
}

function redo() {
    if (!redoStack.length) return;
    undoStack.push(JSON.stringify({ areas, select_areas, zoom_scale, offset_x, offset_y }));
    let s = JSON.parse(redoStack.pop());
    areas = s.areas;
    select_areas = s.select_areas;
    zoom_scale = s.zoom_scale;
    offset_x = s.offset_x;
    offset_y = s.offset_y;
    draw();
}

function getBoundingBox(indices) {
    let minx = Infinity, miny = Infinity;
    let maxx = -Infinity, maxy = -Infinity;

    for (let idx of indices) {
        let p = areas[idx];
        minx = Math.min(minx, p.x1);
        miny = Math.min(miny, p.y1);
        maxx = Math.max(maxx, p.x2);
        maxy = Math.max(maxy, p.y2);
    }
    return { x1: minx, y1: miny, x2: maxx, y2: maxy };
}
function hitResizeHandle(x, y) {
    if (select_areas.length === 0) return -1;

    let b = getBoundingBox(select_areas);
    let area = handle_size / (img_scale * zoom_scale);

    if (Math.abs(x - b.x1) < area && Math.abs(y - b.y1) < area) return 1;
    if (Math.abs(x - b.x2) < area && Math.abs(y - b.y1) < area) return 2;
    if (Math.abs(x - b.x2) < area && Math.abs(y - b.y2) < area) return 3;
    if (Math.abs(x - b.x1) < area && Math.abs(y - b.y2) < area) return 4;
    return -1;
}

// ===== 初期化 =====
window.onload = () => {
    ocrform_img = document.getElementById('bk_img');

    img_scale = Math.min(
        canvas.width / ocrform_img.width,
        canvas.height / ocrform_img.height
    ) || 1;
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

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('wheel', onMouseWheel, { passive: false });
    canvas.addEventListener('contextmenu', e => e.preventDefault());

    document.addEventListener('keydown', e => {
        if (e.ctrlKey && e.key === 'z') undo();
        if (e.ctrlKey && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) redo();
    });

    draw();
    initTable();
};

// ===== 座標変換 =====
function dp2LP(x, y) {
    let scale = canvas.clientWidth / canvas.width;
    return [
        (x / scale - offset_x) / (img_scale * zoom_scale),
        (y / scale - offset_y) / (img_scale * zoom_scale)
    ];
}

function lp2DP(x, y) {
    return [
        x * img_scale * zoom_scale + offset_x,
        y * img_scale * zoom_scale + offset_y
    ];
}

// ===== ヒットテスト =====
function hitTest(x, y) {
    for (let i = areas.length - 1; i >= 0; i--) {
        let p = areas[i];
        if (p.x1 <= x && x <= p.x2 && p.y1 <= y && y <= p.y2) return i;
    }
    return -1;
}

// ===== Mouse =====
function onMouseDown(e) {
    let rect = canvas.getBoundingClientRect();
    // ブラウザ上でのクリック座標
    // 画像上の座標に変換
    let elem1 = document.getElementById('add_mode');
    let elem2 = document.getElementById('select_mode');
    if (elem1.checked){
        act_mode = 1;
    } else if (elem2.checked){
        act_mode = 2;
    } else {
        act_mode = 3;
    }
    let [x, y] = dp2LP(e.clientX - rect.left, e.clientY - rect.top);
    // リサイズ
    let h = hitResizeHandle(x, y);
    if (h > 0) {
        saveState();
        resizing = true;
        resize_handle = h;
        resize_start_bbox = getBoundingBox(select_areas);
        resize_start_areas = JSON.parse(JSON.stringify(
            select_areas.map(i => areas[i])
        ));
        return;
    }
    // パン
    if (e.shiftKey || act_mode == 3) {
        isPanning = true;
        lpx1 = e.clientX;
        lpy1 = e.clientY;
        return;
    }
    // 図形移動
    let hit = hitTest(x, y);
    if (hit !== -1) {
        saveState();

        if (e.ctrlKey) {
            if (!select_areas.includes(hit)) {
                select_areas.push(hit);
            }
        } else {
            select_areas = [hit];
        }
        moving = true;
        move_start_x = x;
        move_start_y = y;
        move_lock_axis = null;
        draw();
        return;
    }
    // handle = -1;
    // if (0 <= x && x <= ocrform_img.width && 0 <= y && y <= ocrform_img.height) {
    // 新規追加
    saveState();
    drag = true;
    lpx1 = lpx2 = x;
    lpy1 = lpy2 = y;
}

function onMouseMove(e) {
    let rect = canvas.getBoundingClientRect();

    if (isPanning) {
        offset_x += e.movementX;
        offset_y += e.movementY;
        draw();
        return;
    }
    let [x, y] = dp2LP(e.clientX - rect.left, e.clientY - rect.top);
    if (resizing) {
        let b0 = resize_start_bbox;
        let b1 = { ...b0 };

        let dx = x - (resize_handle === 1 || resize_handle === 4 ? b0.x1 : b0.x2);
        let dy = y - (resize_handle === 1 || resize_handle === 2 ? b0.y1 : b0.y2);

        // Shift：軸拘束
        if (e.shiftKey) {
            if (Math.abs(dx) > Math.abs(dy)) {
                dy = 0;
            } else {
                dx = 0;
            }
        }

        if (resize_handle === 1 || resize_handle === 4) b1.x1 = b0.x1 + dx;
        if (resize_handle === 2 || resize_handle === 3) b1.x2 = b0.x2 + dx;
        if (resize_handle === 1 || resize_handle === 2) b1.y1 = b0.y1 + dy;
        if (resize_handle === 3 || resize_handle === 4) b1.y2 = b0.y2 + dy;

        let sx = (b1.x2 - b1.x1) / (b0.x2 - b0.x1);
        let sy = (b1.y2 - b1.y1) / (b0.y2 - b0.y1);

        select_areas.forEach((idx, i) => {
            let p0 = resize_start_areas[i];
            let p = areas[idx];

            p.x1 = b1.x1 + (p0.x1 - b0.x1) * sx;
            p.x2 = b1.x1 + (p0.x2 - b0.x1) * sx;
            p.y1 = b1.y1 + (p0.y1 - b0.y1) * sy;
            p.y2 = b1.y1 + (p0.y2 - b0.y1) * sy;
        });

        draw();
        return;
    }

    if (moving) {
        let dx = x - move_start_x;
        let dy = y - move_start_y;
        // Shift：軸拘束
        if (e.shiftKey) {
            if (!move_lock_axis) {
                move_lock_axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
            }
            if (move_lock_axis === 'x') dy = 0;
            if (move_lock_axis === 'y') dx = 0;
        }

        for (let idx of select_areas) {
            let p = areas[idx];
            p.x1 += dx; p.x2 += dx;
            p.y1 += dy; p.y2 += dy;
        }

        move_start_x = x;
        move_start_y = y;
        draw();
        return;
    }

    if (drag) {
        [lpx2, lpy2] = [x, y]
        draw();
        drawCurrent();
    } else {
        let h = hitResizeHandle(x, y);
        if (h == 1) {
            document.body.style.cursor = 'nw-resize';   // 左上
        } else if (h == 2) {
            document.body.style.cursor = 'ne-resize';   // 右上
        } else if (h == 3) {
            document.body.style.cursor = 'se-resize';   // 右下
        } else if (h == 4) {
            document.body.style.cursor = 'sw-resize';   // 左下
        } else {
            document.body.style.cursor = 'default';
        }
    }
}

function onMouseUp() {
    isPanning = false;
    moving = false;
    resize_handle = -1;
    resize_start_bbox = null;
    resize_start_areas = null;
    move_lock_axis = null;

    if (resizing) {
        resizing = false;
        for (let idx of select_areas) {
            let p = areas[idx];
            let minx = Math.min(p.x1, p.x2);
            let miny = Math.min(p.y1, p.y2);
            let maxx = Math.max(p.x1, p.x2);
            let maxy = Math.max(p.y1, p.y2);
            p.x1 = minx;
            p.y1 = miny;
            p.x2 = maxx;
            p.y2 = maxy;
        }
        return;
    }
    if (drag) {
        drag = false;
        // 入力領域の最小サイズ 4
        if (Math.abs(lpx1 - lpx2) > 4 && Math.abs(lpy1 - lpy2) > 4) {
            let x1 = Math.min(lpx1, lpx2);
            let y1 = Math.min(lpy1, lpy2);
            let x2 = Math.max(lpx1, lpx2);
            let y2 = Math.max(lpy1, lpy2);
            if (act_mode == 2) {
                selectRect(x1, y1, x2, y2);
                draw();
                return;
            }
            areas.push({
                x1: x1,
                y1: y1,
                x2: x2,
                y2: y2,
                text: String(++area_no_max)
            });
            select_areas = [areas.length - 1];
        }
        draw();
    }
}

// ===== Zoom =====
function onMouseWheel(e) {
    e.preventDefault();
    let rect = canvas.getBoundingClientRect();
    let [lx, ly] = dp2LP(e.clientX - rect.left, e.clientY - rect.top);

    let delta = e.deltaY < 0 ? 1.1 : 0.9;
    let nz = zoom_scale * delta;
    if (nz < 0.2 || nz > 8) return;

    saveState();
    zoom_scale = nz;

    let [nx, ny] = lp2DP(lx, ly);
    offset_x += (e.clientX - rect.left) - nx;
    offset_y += (e.clientY - rect.top) - ny;

    draw();
}
// 拡大・縮小
// function zoom(zoom) {
//     if (zoom == -1) {
//         if (16 < zoom_base) {
//             saveState();
//             zoom_base /= 2;
//             canvas.width /= 2;
//             canvas.height /= 2;
//             zoom_scale = zoom_base / 256;
//         }
//     } else {
//         if (zoom_base < 4096) {
//             saveState();
//             zoom_base *= 2;
//             canvas.width *= 2;
//             canvas.height *= 2;
//             zoom_scale = zoom_base / 256;
//         }
//     }
//     draw();
// }

// ===== Draw =====
function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(
        ocrform_img,
        offset_x,
        offset_y,
        ocrform_img.width * img_scale * zoom_scale,
        ocrform_img.height * img_scale * zoom_scale
    );
    ctx.font = String(40 * img_scale * zoom_scale) + "px 'ＭＳ ゴシック'";
    ctx.fillStyle = 'red';
    ctx.textBaseline = 'top';

    for (let i = 0; i < areas.length; i++) {
        let p = areas[i];
        // let [x, y] = lp2DP(p.x1, p.y1);
        // let [w, h] = lp2DP(p.x2 - p.x1, p.y2 - p.y1);
        let [x1, y1] = lp2DP(p.x1,p.y1);
        let [x2, y2] = lp2DP(p.x2,p.y2);
        let [x, y] = [Math.min(x1, x2), Math.min(y1, y2)];
        let [w, h] = [Math.abs(x1 - x2), Math.abs(y1 - y2)];

        ctx.strokeStyle = select_areas.includes(i) ? '#0000FF' : 'red';
        ctx.lineWidth = select_areas.includes(i) ? 3 : 2;
        ctx.strokeRect(x, y, w, h);
        drawAreaNo(x, y, p.text);
    }
    drawSelectionHandles();
}

function drawCurrent() {
    let [x1, y1] = lp2DP(lpx1,lpy1);
    let [x2, y2] = lp2DP(lpx2,lpy2);
    let [x, y] = [Math.min(x1, x2), Math.min(y1, y2)];
    let [w, h] = [Math.abs(x1 - x2), Math.abs(y1 - y2)];
    // let [x, y] = lp2DP(Math.min(lpx1, lpx2), Math.min(lpy1, lpy2));
    // let [w, h] = lp2DP(Math.abs(lpx1 - lpx2), Math.abs(lpy1 - lpy2));
    ctx.strokeStyle = 'deepskyblue';
    ctx.strokeRect(x, y, w, h);
}
function drawSelectionHandles() {
    if (select_areas.length === 0) return;

    let b = getBoundingBox(select_areas);
    let [x1, y1] = lp2DP(b.x1, b.y1);
    let [x2, y2] = lp2DP(b.x2, b.y2);

    let s = handle_size;
    ctx.strokeStyle = '#0000FF';
    ctx.lineWidth = 1;

    ctx.strokeRect(x1 - s, y1 - s, s * 2, s * 2);
    ctx.strokeRect(x2 - s, y1 - s, s * 2, s * 2);
    ctx.strokeRect(x2 - s, y2 - s, s * 2, s * 2);
    ctx.strokeRect(x1 - s, y2 - s, s * 2, s * 2);
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
// function drawTable(x, y, w, h) {
//     let startx = x;
//     let starty = y;
//     let endx = startx + w;
//     let endy = starty + h;
//     if (table_row < 1) {
//         table_row = 1;
//     }
//     let div_w = w;
//     let div_h = h / table_row;
//     ctx.beginPath();
//     ctx.strokeStyle = 'green';
//     for (let i = 1; i < table_row; i++) {
//         ctx.moveTo(startx, starty + div_h * i);
//         ctx.lineTo(endx, starty + div_h * i);
//     }
//     ctx.lineWidth = 1;
//     ctx.stroke();

//     ctx.beginPath();
//     ctx.rect(x, y, w, h);
//     ctx.strokeStyle = 'red';
//     ctx.lineWidth = 2;
//     ctx.stroke();

// }
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
        saveState();
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
// function actMode(btn) {
//     if (act_mode == 1) {
//         btn.textContent  = '枠選択';
//         act_mode = 2;
//     } else {
//         btn.textContent  = '枠入力';
//         act_mode = 1;
//     } 
// }

// function selectAll(btn) {
//     select_areas = [];
//     if (!selected_all) {
//         let len = areas.length;
//         for (let i = len - 1; 0 <= i; i--) {
//             select_areas.push(i);
//         }
//         btn.textContent  = '選択解除';
//     } else {
//         btn.textContent  = '全選択';
//     } 
//     selected_all = !selected_all;
//     draw();
// }
// function selectHandle() {
//     handle = -1;
//     if (select_areas.length != 1) {
//         return;
//     }
//     let selectIdx = select_areas[0];
//     let len = areas.length;
//     let [area, dmy] = dp2LP(handle_size, 1);  // 5px * 2 の領域で選択判定
//     let p = areas[selectIdx];
//     if (p.x1 - area < lpx1 && lpx1 < p.x1 + area && p.y1 - area < lpy1 && lpy1 < p.y1 + area) {
//         handle = 1;
//     } else if (p.x2 - area < lpx1 && lpx1 < p.x2 + area && p.y1 - area < lpy1 && lpy1 < p.y1 + area) {
//         handle = 2;
//     } else if (p.x2 - area < lpx1 && lpx1 < p.x2 + area && p.y2 - area < lpy1 && lpy1 < p.y2 + area) {
//         handle = 3;
//     } else if (p.x1 - area < lpx1 && lpx1 < p.x1 + area && p.y2 - area < lpy1 && lpy1 < p.y2 + area) {
//         handle = 4;
//     }
//     // handle = -1;
// }
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
    let input_row = document.getElementById( 'table_row' ).value;
    let row_str = conv_num(input_row);
    table_row = Number(row_str);
    let table_name = document.getElementById( 'table_name' ).value.trim();
    // let table_no = document.getElementById( 'table_no' ).value;
    // let col_no = document.getElementById( 'col_no' ).value;
    let table_json = document.getElementById( 'table_json' ).value.trim();
    let item_name = document.getElementById( 'item_name' ).value.trim();
    let item_json = document.getElementById( 'item_json' ).value.trim();
    dialog_table.close();
    addTableItem(table_name, table_json, item_name, item_json);
}
function dialog_table_close() {
  dialog_table.close();
}
