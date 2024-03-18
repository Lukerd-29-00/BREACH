const params = new URLSearchParams(new URL(window.location.href).search)

const loc = params.get('location') !== null ? params.get('location') : 'US'

fetch("/locations.json").then(r => {
    r.json().then(js => {
        document.getElementById("price").textContent = `${decodeURI(loc)}: ${js[loc]}`
    })
}).catch(e => {
    
})