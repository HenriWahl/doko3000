let myname = ''

$(document).ready(function () {
    const socket = io({path: '/doko3000'})

    let dragging = dragula([document.querySelector('#hand'), document.querySelector('#table')]);

    dragging.on('drop', function(el) {
        console.log(el.id)
        console.log(el.parentNode.id)
        socket.emit('played-card', {card: el.id, username: myname})
    })

    socket.on('connect', function () {
        socket.emit('my event',
            {data: 'I\'m connected!'})

        socket.emit('whoami')
    })

    socket.on('you-are-what-you-is', function (msg) {
        if (myname == '') {
            myname = msg.username
            console.log(myname)
        }
    })

    socket.on('my response', function (msg) {
        console.log(msg.data)
    })

    socket.on('table_available', function (msg) {
        console.log('yo')
        console.log(msg.data)
    })

    socket.on('thread_test', function (msg) {
        console.log('yolo')
        console.log(msg.data)
        console.log(myname)
    })

    socket.on('new-table-available', function (msg) {
        console.log(msg)
        console.log('myname:', myname)
        console.log(myname, msg.username, myname != msg.username)
        if (myname != msg.username) {
            console.log(msg.username, 'testbutton')
        }
        $('#available_tables').html(msg.html)
    })

        socket.on('played-card-by-user', function (msg) {
        console.log(msg)
        console.log('myname:', myname)
        console.log(myname, msg.username, myname != msg.username)
        if (myname != msg.username) {
            console.log(msg.username, msg.card)
            $('#table').append($('#' + msg.card))
        }
    })


    $(document).on('click', '#new_table', function () {
        console.log('new table')
        socket.emit('new-table', {button: 'new_table'})
    })

    $(document).on('click', '.list-item-table', function () {
        console.log(this)
        console.log($(this).data('table'))
        socket.emit('enter-table', {username: myname,
                                    table: $(this).data('table')})
    })

})