const $modal = document.getElementById('del-record');
const $openButton = document.querySelectorAll('#open');
const $closeButton = document.querySelectorAll('#close');
const $deleteButton = document.querySelectorAll('#delete');
const $scondeleteButton = document.querySelectorAll('#scon_delete');
let $deleteFlg = false;

for (let i = 0; i < $openButton.length; i++) {
  $openButton[i].addEventListener('click', (e) => {
    // e.stopPropagation();
    // $modal.showModal();
    $deleteFlg = true;
  });
}

for (let i = 0; i < $closeButton.length; i++) {
  $closeButton[i].addEventListener('click', () => {
    $modal.close();
  });
}
for (let i = 0; i < $deleteButton.length; i++) {
  $deleteButton[i].addEventListener('click', () => {
    $modal.close();
    delete_evidence_list();
  });
}
for (let i = 0; i < $scondeleteButton.length; i++) {
  $scondeleteButton[i].addEventListener('click', () => {
    $modal.close();
    delete_evidence();
  });
}
