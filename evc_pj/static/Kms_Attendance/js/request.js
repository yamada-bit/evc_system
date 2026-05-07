// CSSの :nth-child() は常にDOM上の構造（見た目ではなくHTMLの位置）を基にして判定します。
// そのため、非表示にしても nth-child(odd) の判定には影響しません。
// 表示されている行の中で奇数・偶数」を制御するにはJavaScriptでDOMを操作する必要があります。
function row_odd_even() {
    const rows = document.querySelectorAll('#edit_table tr');
    let visibleIndex = 0;
  
    rows.forEach(row => {
      if (row.style.display !== 'none') {
        row.style.backgroundColor = (visibleIndex % 2 === 0) ? 'rgb(219, 247, 239' : '#ffffff';
        visibleIndex++;
      }
    });
}
$(function () {
    $('#add_extra_rest').on('click', function () {
        var idx = 2;
        var prev = $($('#rest_0_tr').prev());
        if (prev.hasClass('extra-rest-tr')) {
            var newIdx = parseInt(prev.attr("id").replace("extra_rest_tr", ""));
            if(!isNaN(newIdx)){idx = newIdx + 1; }
        }
        var tmp = $('#rest_0_tr');
        var tr_id = "extra_rest_tr" + idx;
        var h = '<tr id="' + tr_id + '" class="extra-rest-tr">' + tmp.html().replace(/rest0/g, 'rest' + idx) + '</tr>';
        h = h.replace(/rest_no/g, '休憩' + (idx));
        $($('table')[0]).append(h);
        $('#' + tr_id).insertBefore('#rest_0_tr');

        var prev = $($('#rest_0_tr').prev());
        $(prev.children()[1]).append($(this));

        $(".extra-rest-tr .remove-extra-rest").click(removeExtrarestTr);

        $('#next_day_start_rest'+idx).val(idx);
        $('#next_day_end_rest' + idx).val(idx);
        movePlusButton();

    });
    var movePlusButton = function () {
        var rest0 = $('#rest_0_tr');
        var plusButton = $('#add_extra_rest');
        if (rest0.length > 0) {
            var prev = $(rest0.prev());
            if (prev.length > 0) {
                $(prev.children()[1]).append(plusButton);
            }
        }
        row_odd_even();
    };

    var removedIds = [];
    var removeExtrarestTr = function(){
        var rest0 = $('#rest_0_tr');
        var plusButton = $('#add_extra_rest');
        $(rest0.children()[1]).append(plusButton);

        var tr = $($(this).parent().parent().parent());
        var id = $($('#' + tr.attr('id') + ' input[type=hidden]')[0]).val();
        if(id){removedIds.push(id); }
        $('#removed_ids').val(removedIds.join(','));

        tr.remove();

        var prev = $(rest0.prev());
        $(prev.children()[1]).append(plusButton);
        row_odd_even();
    };

    movePlusButton();
    $(".extra-rest-tr .remove-extra-rest").click(removeExtrarestTr);

    $('#add_extra_rest_org').click(function(){
        if("true" == $("#holiday").val()){return}; // 勤務区分が休暇設定の場合は追加させない

        var idx = 2;
        var prev = $($('#rest_0_tr').prev());
        if (prev.hasClass('extra-rest-tr')) {
            var newIdx = parseInt(prev.attr("id").replace("extra_rest_tr", ""));
            if(!isNaN(newIdx)){idx = newIdx + 1; }
        }

        var tmp = $('#rest_0_tr');
        var tr_id = "extra_rest_tr" + idx;
        var h = '<tr id="' + tr_id + '" class="extra-rest-tr">' + tmp.html().replace(/rest0/g, 'rest' + idx) + '</tr>';
        h = h.replace(/rests\[0\]/g, 'rests[' + idx +']');
        h = h.replace(/休憩0/g, '休憩' + (idx));
        h = h.replace(/\(0\)/g, '('+idx+')');
        $($('table')[0]).append(h);
        $('#' + tr_id).insertBefore('#rest_0_tr');

        var prev = $($('#rest_0_tr').prev());
        $(prev.children()[1]).append($(this));

        $(".extra-rest-tr .remove-extra-rest").click(removeExtrarestTr);

                        //$(".rests").timepicker({step: "5", timeFormat: "H:i", maxTime: "23:45"});
        $('#' + tr_id + ' input').removeAttr("disabled");
        $('#idx_rest'+idx).val(idx);
        $('#next_day_start_rest'+idx+'_n').val(idx);
        $('#next_day_end_rest'+idx+'_n').val(idx);
        return false;
    });
});
