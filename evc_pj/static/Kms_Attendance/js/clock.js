//function time(){
//    var now = new Date();
//    document.getElementById("time").innerHTML = now.toLocaleString();
//}
//setInterval('time()', 1000);

function showTime(){
    var now = new Date();
    //document.getElementById("showTime").innerHTML = now.toLocaleString();
    document.getElementById("showTime2").value = now.toLocaleString();
}
showTime();
setInterval('showTime()',1000);
