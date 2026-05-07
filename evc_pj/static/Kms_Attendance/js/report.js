$(function () {
    $.datepicker.setDefaults($.datepicker.regional["ja"]);
    $("#date").datepicker();
    $('#searchForm').find('select').change(function () {
        document.search_form.submit();
    });

    $('#per').change(function () {
        document.search_form.submit();
    });

    //$('#searchForm').submit(function () {
    //    $(this).attr('action', '/aggregates/' + $('#select_date').val());
    //    $('#select_date').prop('disabled', true);

    //    // 未入力は除外
    //    $(this).find('input').each(function () {
    //        if (["text", "hidden", "radio", "number"].indexOf($(this).prop('type')) !== -1 && $(this).val() == "") {
    //            $(this).prop('disabled', true);
    //        } else if ($(this).prop('type') == "checkbox" && $(this).prop('checked') == false) {
    //            $(this).prop('disabled', true);
    //        }
    //    });

    //    $(this).find('select').each(function () {
    //        if ($(this).val() == "") {
    //            $(this).prop('disabled', true);
    //        }
    //    });

    //    if ($('#download_type').val() == '') {
    //        $('#page').prop('disabled', true);
    //    }
    //});

    $('#searchForm').find('input[type=text]').keypress(function (e) {
        if (e.which == 13) {
            $('#searchForm').submit();
        }
    });

    $('#searchForm').find('input, select').not('#select_date').change(function () {
        $('#searchForm').submit();
    });

    $('#searchForm').find('#prev_date').bind('click', function () {
        $('#select_date').val('2021-11');
        $('#searchForm').submit();
    });

    $('#searchForm').find('#next_date').bind('click', function () {
        $('#select_date').val('2022-01');
        $('#searchForm').submit();
    });

    $('#searchForm').find('#csv_download').bind('click', function () {
        $('#download_type').val('csv');
        $('#searchForm').submit();
    });

    $('#searchForm').find('#per').change(function () {
        $('#searchForm').submit();
    });

});
$("#update_output, #update_output_with_create").bind("click", function () {
    var id = $(this).attr("id");
    var create = false;
    var message = "レポートデータを更新してもよろしいですか？\n(月次・残業管理・36協定レポート共通)\n\n※月締確定状態の社員のデータは更新されません。\n※表示中の月の、全社員のデータが更新されます。絞り込みは適用されません。";
    if (id == "update_output_with_create") {
        create = true;
        message += "\n日次勤怠データが未生成の場合に生成も同時に行います。社員の人数によって処理に時間がかかる可能性がありますのでご注意ください。";
    }
    if (confirm(message)) {
        $.ajax({
            type: "get",
            url: "/outputs/update_output",
            data: {
                'date': "2021-12",
                'create': create
            },
            success: function (data) {
                alert(data.msg);
            }
        });
    }
});

$('#date').change(function () {
    var date = $(this).val();
    document.search_form.submit();
});
