$(function() {
    $('#uploadform').submit(function() {
      // const element = document.getElementById('upload_area2');
      // element.remove();
      let fileList = document.getElementById('file_upload').files;
      if (fileList.length < 1) {
        alert('ファイルが選択されていません');
        return false;
      }
    });
    $( 'input[name="evidence_kubuns"]:radio' ).change( function() {
      let radioval = $(this).val();
      changeKubun(radioval)
    });
    let isComposing = false;
    let specifElm = document.getElementById('id_specif');
    specifElm.addEventListener('compositionstart', function() {
      isComposing = true;
    });
    specifElm.addEventListener('compositionend', function() {
      isComposing = false;
      let value = checkSpecif(specifElm.value);
      specifElm.value = value;
    });
    $('#id_specif').on('input', function() {
      if (isComposing)
        return;
      let value = checkSpecif($(this).val());
      $(this).val(value);
    });
    $('#id_specif').focus(function() {
      isComposing = false;
      document.getElementById('id_evidence_kubuns_2').checked = true;
      changeKubun('specif')
    });
});
let isSubmit = false;
function check(btn) {
    if (isSubmit) {
        show_message('処理中です');
        return false;
    } else {
        if (document.getElementById('id_ocrform') != null) {
            if (document.getElementById('id_ocrform').value == '0') {
                show_message('フォームが選択されていません');
                return false;
            }
        }
        let fileList = document.getElementById('file_upload').files;
        if (fileList.length < 1) {
            show_message('ファイルが選択されていません');
            return false;
        }
        if (document.getElementById('id_evidence_kubuns_2').checked) {
            if (document.getElementById('id_specif').value == '') {
                show_message('ページ番号が入力されていません');
                return false;
            }
        }

        isSubmit = true;
        btn.value = '処理中';
        return true;
    }
};
function area(btn) {
    if (isSubmit) {
        show_message('処理中です');
        return false;
    } else {
        let fileList = document.getElementById('file_upload').files;
        if (fileList.length < 1) {
            show_message('ファイルが選択されていません');
            return false;
        }
        if (1 < fileList.length) {
            show_message('1ファイルだけ選択してください');
            return false;
        }
        isSubmit = true;
        btn.value = '処理中';
    // document.getElementById( 'submit_action1' ).value = 'area';
    // $('#uploadform').submit();
    // if (btn.id == 'btn_cropimage') {
    //   setImageData();
    // }
        return true;
    }
}

//dragoverはファイルがドラッグされて、要素の上に重なったときに発生するイベント。
//ブラウザが直接ドラッグされたファイルを開かないようにしている。
//背景色を緑にしている。
document.getElementById('upload_area').addEventListener('dragover', function (e) {
    e.preventDefault();
    this.style.backgroundColor = '#80ff80';
});

//ドラッグしていたファイルが要素から離れた場合に呼び出されるイベント。背景色を元に戻している。     
document.getElementById('upload_area').addEventListener('dragleave', function () {
    this.style.backgroundColor = '';
});

//ドラッグしていたファイルが要素から離れた場合に呼び出されるイベント。背景色を元に戻している。
document.getElementById('upload_area').addEventListener('drop', function (e) {
    e.preventDefault();
    this.style.backgroundColor = '';
    if (isSubmit) {
        show_message('処理中です');
        return;
    }
// event.dataTransfer.files をINPUT要素である file_upload にコピーしている。
    if (e.dataTransfer.files.length > 0) {
        let obj = document.getElementById('file_upload');
        obj.files = e.dataTransfer.files;
    // document.getElementById('file_upload').dispatchEvent(new Event('change'));

        loadfile(obj)
    }
});
let isEvidenceKubun = false;
let evidence = document.getElementsByClassName('card-evidence');
if (0 < evidence.length) {
    isEvidenceKubun = true;
}
let isPreview = false;
// let preview = document.getElementsByClassName('preview-area');
// if (0 < preview.length) {
//   isPreview = true;
// }

let data_transfer = new DataTransfer();
let key = 0;
function loadfile(obj) {
    if (isSubmit) {
        // 処理中はファイルの追加はしない
        // show_message('処理中です');
        return;
    }

    for (let i = 0; i < obj.files.length; i++) {
        let FileName =  obj.files[i].name;

        // alert('obj ' + FileName)
        // 同一ファイル名をチェック
        let duplicate = false;
        for (let j = 0; j < data_transfer.files.length; j++) {
            if (FileName === data_transfer.files[j].name) {
                duplicate = true;
                break;
            }
        }
        if (duplicate) {
            // alert('duplicate ' + FileName)
            continue;
        }
        if (checkExt(FileName)) {
            let field = document.getElementById('upload_area2');
            let figure = document.createElement('figure');
            let rmBtn = document.createElement('input');
            let newElement = document.createTextNode(FileName);
            rmBtn.type = 'button';
            rmBtn.name = key;
            rmBtn.value = '削除';
            rmBtn.onclick = (function () {
                if (isSubmit) {
                    // show_message('処理中です');
                    return;
                }
                let element = document.getElementById('btn-' + String(this.name));
                if (element != null) {
                    let name = element.textContent;
                    element.remove();
                    // 一部ファイルを削除
                    // 新しくDataTransferを作り必要なファイルをaddし元のfilesを上書き                    
                    let dt = new DataTransfer();
                    let files = data_transfer.files;
                    for (let i = 0; i < files.length; i++) {
                        let file = files[i];
                        if (file.name != name) {
                            dt.items.add(file);
                        }
                    }
                    data_transfer = dt;
                    // data_transfer = new DataTransfer()
                    // for (let i = 0; i < dt.files.length; i++) {
                    //     data_transfer.items.add(dt.files[i]);
                    // }
                    obj.value = '';
                    obj.files = data_transfer.files;
                    // alert(name + ' remove ' + data_transfer.files.length + ':' + document.getElementById('file_upload').files.length);
                    if (obj.files.length < 2) {
                        let area = document.getElementById('btn_area');
                        area.disabled = false
                        let area2 = document.getElementById('btn_cropimage');
                        area2.disabled = false
                        let area_msg = document.getElementsByClassName('area-msg');
                        if (0 < area_msg.length) {
                            area_msg[0].style.display ='block';
                        }
                        if (obj.files.length === 1) {
                            resizeImage(obj.files[0]);  // base64画像データ・サムネイル画像作成
                        } else {
                            clearImage();   // 画像データクリア
                        }
                        if (isEvidenceKubun) {
                            // evidence[0].style.display ='block';
                            document.getElementById('id_evidence_kubuns_0').disabled = false;
                            document.getElementById('id_evidence_kubuns_1').disabled = false;
                            document.getElementById('id_evidence_kubuns_2').disabled = false;
                            document.getElementById('id_specif').disabled = false;
                            if (obj.files.length === 0) {
                                document.getElementById('id_evidence_kubuns_0').checked = true;
                                document.getElementById('id_specif').value = '';
                            }
                        }
                    }
                }
            });
            figure.setAttribute('id', 'btn-' + key);
            figure.appendChild(newElement);
            figure.appendChild(rmBtn);
            field.appendChild(figure);

            // var fr = new FileReader();
            // var img = document.createElement('img');
            // fr.tmpImg = img;
            // fr.onload = function () {
            //   this.tmpImg.src = this.result;
            //   this.tmpImg.onload = function () {
            //     figure.appendChild(this);
            //     field.appendChild(figure);
            //   }
            // }
            // // 画像読み込み
            // fr.readAsDataURL(obj.files[i]);
            
            data_transfer.items.add(obj.files[i]);
            key++;
        } else {
          show_message(FileName + ' : ファイル形式が違います！');
        }
    }
    obj.value = '';
    obj.files = data_transfer.files;
    // 画像分割ボタン：複数ファイルの場合は無効
    if (1 < obj.files.length) {
        let area = document.getElementById('btn_area');
        area.disabled = true
        let area2 = document.getElementById('btn_cropimage');
        area2.disabled = true
        let area_msg = document.getElementsByClassName('area-msg');
        if (0 < area_msg.length) {
            area_msg[0].style.display ='none';
        }
        if (isEvidenceKubun) {
            // evidence[0].style.display ='none';
            document.getElementById('id_evidence_kubuns_0').disabled = true;
            document.getElementById('id_evidence_kubuns_1').disabled = true;
            document.getElementById('id_evidence_kubuns_2').disabled = true;
            document.getElementById('id_specif').disabled = true;
            document.getElementById('id_evidence_kubuns_0').checked = true;
            document.getElementById('id_specif').value = '';
        }
    }
    if (obj.files.length === 1) {
        resizeImage(obj.files[0]);  // base64画像データ・サムネイル画像作成
    } else {
        clearImage();   // 画像データクリア
    }
}
// ファイル形式のチェック
function checkExt(filename) {
    var pos = filename.lastIndexOf('.');
    if (pos === -1)
        return false;
    var ext = filename.slice(pos + 1).toLowerCase();
    if (ext === 'pdf' || ext === 'png' || ext === 'jpeg' || ext === 'jpg' || ext === 'gif' || ext === 'bmp')
        return true;
    if (ext === 'tif' || ext === 'tiff')
        return true;
    return false;
}
function checkPdf(filename) {
    var pos = filename.lastIndexOf('.');
    if (pos === -1)
        return false;
    var ext = filename.slice(pos + 1).toLowerCase();
    if (ext === 'pdf')
        return true;
    return false;
}
function changeKubun(val) {
    if (val == 'file') {
        if (isEvidenceKubun) {
            document.getElementById('id_specif').value = '';
        }
    } else if (val == 'specif') {
    } else {
        if (isEvidenceKubun) {
            document.getElementById('id_specif').value = '';
        }
    }
}
function checkSpecif(val) {
    value = val.replace(/[‐－―ー]/g, '-').replace('，', ',');
    value = value.replace(/[０-９]/g, function(s) {
      return String.fromCharCode(s.charCodeAt(0) - 65248);
    }).replace(/[^0-9\-\,]/g, '');
    return value;
}
// プレビューPDF表示
function pdf_thumnail(fileData) {
    let object = document.getElementById('id_pdfthumb');
    // FileReaderオブジェクトを使ってファイル読み込み
    let reader = new FileReader();
    // ファイル読取り成功時処理
    reader.onload = function() {
        object.src = reader.result;
        $('#id_pdfthumb').show();
        $('#preview_area').show();
    }
    // ファイル読み込みを実行
    reader.readAsDataURL(fileData);
}
// プレビュー画像表示
function img_preview(fileData) {
    let object = document.getElementById('id_preview_img');
    // FileReaderオブジェクトを使ってファイル読み込み
    let reader = new FileReader();
    // ファイル読取り成功時処理
    reader.onload = function() {
        object.src = reader.result;
        $('#id_preview_img').show();
        $('#preview_area').show();
    }
    // ファイル読み込みを実行
    reader.readAsDataURL(fileData);
}
// base64画像データ・サムネイル画像クリア
function clearImage() {
    $('#file_photo').attr('value', '');
    $('.thumb-area').hide();
    // $('.thumb_area').remove();
    // プレビュー非表示
    if (isPreview) {
        $('#id_preview_img').hide()
        $('#id_pdfthumb').hide();
        $('#preview_area').hide();
    }
}

const THUMBNAIL_WIDTH = 2400;
const THUMBNAIL_HEIGHT = 2400;

// base64画像データ・サムネイル画像作成
function resizeImage(file) {
    clearImage();
    if (typeof file === 'undefined') {
        // 削除でデータがない場合は処理しない
        return;
    }
    // スマホボタンが表示されていて押下可能かどうか
    if ($('#btn_cropimage').css('display') === 'block') {
        let result = $('#btn_cropimage').prop('disabled');
        if(result) {
            return;
        }
    } else {
        // プレビュー表示
        if (isPreview) {
            $('#id_msg').hide()
            if (file.type == 'application/pdf') {
                if (1024*1024 < file.size) {
                    $('#id_msg').show()
                    $('#preview_area').show();
                    return;
                }
                pdf_thumnail(file);
            }
            if (file.type == 'image/jpeg' || file.type == 'image/png') {
                img_preview(file);
            }
        }
        return;
    }
    // if (!file.type.startsWith('image/')) {
    //     return;
    // }
    if (file.type != 'image/jpeg' && file.type != 'image/png') {
        return;
    }
    let img = new Image();  // base64データ作成のためcanvasに描画する画像
    let reader = new FileReader();
    let orientation;
    reader.onload = function(e) {
        img.onload = function() {
            // let width;
            // let height;
            // if (img.width < img.height) {
            //     if (THUMBNAIL_HEIGHT < img.height) {
            //         var ratio = img.width / img.height;
            //         width = THUMBNAIL_HEIGHT * ratio;
            //         height = THUMBNAIL_HEIGHT;
            //     } else {
            //         width = img.width;
            //         height = img.height;
            //     }
            // } else {
            //     if (THUMBNAIL_WIDTH < img.width) {
            //         var ratio = img.height/img.width;
            //         width = THUMBNAIL_WIDTH;
            //         height = THUMBNAIL_WIDTH * ratio;
            //     } else {
            //         width = img.width;
            //         height = img.height;
            //     }
            // }
            // var canvas = $('#canvas')
            //              .attr('width', width)
            //              .attr('height', height);
            // var ctx = canvas[0].getContext('2d');
            // ctx.clearRect(0, 0, width, height);
            // ctx.drawImage(img, 0, 0, img.width, img.height, 0, 0, width, height);
            let canvas = $('#canvas');  // $()はDOM要素の配列を返すcanvas[0]でDOM要素を取得する
            drawCanvas(canvas, THUMBNAIL_WIDTH, img);
            let canvas2 = $('#thumb_canvas');
            drawCanvas(canvas2, 200, img);
                         
            $('.thumb-area').show();    // サムネイル表示
            setImageData(); // Base64データ作成
        }
        img.src = e.target.result;  // base64形式にエンコードされたURLをimg要素のsrc属性に指定
        // $('#thumb_area').html('<img src="' + e.target.result + '">')    // サムネイル画像
    };
    reader.readAsDataURL(file)
    // FIle型のファイルを読み込んでresult属性にファイルのurlを格納(ファイルを、Data URIとして読み込む)
}
// 縦横比を固定で指定ピクセル内にリサイズして描画
function drawCanvas(canvas, maxpix, img) {
    let width;
    let height;
    if (img.width < img.height) {
        if (maxpix < img.height) {
            let ratio = img.width / img.height;
            width = maxpix * ratio;
            height = maxpix;
        } else {
            width = img.width;
            height = img.height;
        }
    } else {
        if (maxpix < img.width) {
            let ratio = img.height/img.width;
            width = maxpix;
            height = maxpix * ratio;
        } else {
            width = img.width;
            height = img.height;
        }
    }
    canvas.attr('width', width);
    canvas.attr('height', height);
    let ctx = canvas[0].getContext('2d');   // ここでのcanvasはDOM要素の配列canvas[0]でDOM要素を取得する
    ctx.clearRect(0, 0, width, height);
    ctx.drawImage(img, 0, 0, img.width, img.height, 0, 0, width, height);
}
// Canvasで描画した画像をBase64へ変換
function setImageData() {
    let canvas = document.getElementById('canvas');
    // GoogleのWebパフォーマンス改善ガイドではJpegの品質は85(以下)にすることを推奨
    // Base64への変換 元サイズより33%データ量が増える。
    let base64Data = canvas.toDataURL('image/jpeg', 0.80); // 画質0.80
    // let base64Data = canvas.toDataURL('image/jpeg', 0.85); // 画質0.85
    // キャンパスに描画されている現在の内容をJPGのデータURIで取得する(BASE64でエンコードされたデータ)
    $('#file_photo').attr('value', base64Data);
}
function toBlob() {
    let canvas = document.getElementById('canvas');
    let base64Data = canvas.toDataURL('image/jpeg', 0.85);
    // Base64からバイナリへ変換
    let bin = atob(base64Data.split('base64,')[1]);
    let buffer = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) {
        buffer[i] = bin.charCodeAt(i);
    }
    // Blobを作成
    let blob = new Blob([buffer], {type: 'image/jpeg'});
    return blob;
}