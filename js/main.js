
function storeDetails() {
    
    $.ajax({
        type:"GET",
        url: "/pubmed/search",
        success:function(data){
            alert('Your browser do not support local storage');
        },
        error:function(xhr){
            handleAjaxError(xhr)
        }
    });
}