var form_count = {{ formset.total_form_count }};

function test() {
    var new_form = '{{formset.empty_form|escapejs}}'.replace(/__prefix__/g, form_count);
    $('#form_set').append(new_form)
    form_count++;
    $('#id_form-TOTAL_FORMS').val(form_count);
    alert('test')
}