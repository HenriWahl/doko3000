$(document).ready(function () {
    const socket = io({path: '/doko3000'})

    socket.on('connect', function () {
        socket.emit('my event',
            {data: 'I\'m connected!'})
    })

    socket.on('my response', function (msg) {
        console.log(msg.data)
    })

    socket.on('session_available', function (msg) {
        console.log('yo')
        console.log(msg.data)
    })

    socket.on('thread_test', function (msg) {
        console.log('yolo')
        console.log(msg.data)
    })
})