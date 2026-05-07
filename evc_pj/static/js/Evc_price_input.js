const input = document.getElementById('id_amount');
// const error = document.getElementById('amount_error');
if (input) {
    let isComposing = false;
    /* =========================
    IME対策
    ========================= */
    input.addEventListener('compositionstart', () => {
    isComposing = true;
    });
    input.addEventListener('compositionend', (e) => {
    isComposing = false;
    sanitize(e.target);
    });
    /* =========================
    入力中処理
    ========================= */
    input.addEventListener('input', (e) => {
    if (isComposing) return;
    sanitize(e.target);
    });
    /* =========================
    確定時フォーマット
    ========================= */
    input.addEventListener('blur', (e) => {
    let value = toHalfWidth(e.target.value);
    if (value === '') {
        // error.textContent = '';
        return;
    }
    // カンマ削除
    const numbers = value.replace(/,/g, '');
    //   if (!/^\d+$/.test(numbers)) {
    //     error.textContent = '数字のみ入力してください';
    //     return;
    //   }
    // 3桁カンマ区切りに変換
    e.target.value = Number(numbers).toLocaleString('ja-JP');
    //   error.textContent = '';
    });
}
/* =========================
   共通処理
========================= */
// 全角数字を半角に変換
function toHalfWidth(str) {
  return str
    .replace(/[０-９]/g, s =>
      String.fromCharCode(s.charCodeAt(0) - 0xFEE0)
    )
    .replace(/，/g, ',');
}
function sanitize(el) {
  let value = toHalfWidth(el.value);
  // 数字とカンマ以外を除去
  value = value.replace(/[^\d,]/g, '');
  el.value = value;
}