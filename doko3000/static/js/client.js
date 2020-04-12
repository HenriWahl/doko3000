let username = ''

$(document).ready(function () {
    const socket = io()

    let dragging = dragula([document.querySelector('#hand'), document.querySelector('#table')]);

    dragging.on('drop', function (el) {
        console.log(el.id)
        console.log(el.parentNode.id)
        socket.emit('played-card', {card: el.id, username: username})
    })

    socket.on('connect', function () {
        socket.emit('my event',
            {data: 'I\'m connected!'})

        socket.emit('whoami')
    })

    socket.on('you-are-what-you-is', function (msg) {
        if (username == '') {
            username = msg.username
            console.log(username)
        }
    })

    socket.on('new-table-available', function (msg) {
        console.log(msg)
        console.log('username:', username)
        console.log(username, msg.username, username != msg.username)
        if (username != msg.username) {
            console.log(msg.username, 'testbutton')
        }
        $('#list_tables').html(msg.html)
    })

    socket.on('played-card-by-user', function (msg) {
        console.log(msg)
        console.log('username:', username)
        console.log(username, msg.username, username != msg.username)
        if (username != msg.username) {
            console.log(msg.username, msg.card)
            $('#table').append($('#' + msg.card))
        }
    })

    socket.on('grab-your-cards', function (msg) {
        console.log(msg)
        socket.emit('my-cards-please', {username: username,
                                        table: msg.table})
    })

    socket.on('your-cards-please', function (msg) {
        console.log(msg)
    })

    $(document).on('click', '#new_table', function () {
        console.log('new table')
        socket.emit('new-table', {button: 'new_table'})
    })

    $(document).on('click', '.list-item-table', function () {
        console.log(this)
        console.log($(this).data('table'))
        socket.emit('enter-table', {
            username: username,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#deal_cards', function () {
        console.log('deal cards')
        socket.emit('deal-cards', {username: username,
                                   table: $(this).data('table')})
    })


})