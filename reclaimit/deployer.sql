create table category
(
    id   int auto_increment
        primary key,
    name varchar(128) not null
);

insert into category (name) values ('Laptops');
insert into category (name) values ('Mobile Devices');
insert into category (name) values ('Tablets');
insert into category (name) values ('Accessories');
insert into category (name) values ('Wallets');
insert into category (name) values ('Keys');
insert into category (name) values ('Bags');
insert into category (name) values ('Others');

create table items
(
    id          int auto_increment
        primary key,
    description varchar(2048) default 'Item found'      null,
    categoryId  int                                     null,
    name        varchar(256)  default 'Item found'      null,
    created_at  datetime      default CURRENT_TIMESTAMP null,
    created_by  varchar(128)  default 'admin'           null
);

create table itemAttachments
(
    id       int auto_increment
        primary key,
    filename text not null,
    itemId   int  not null,
    constraint itemAttachments_items_id_fk
        foreign key (itemId) references items (id)
            on delete cascade
);

create table notification
(
    id         int auto_increment
        primary key,
    title      varchar(128)     not null,
    subtitle   varchar(256)     not null,
    content    varchar(2048)    not null,
    categoryId int              null,
    sentEmail  bit default b'0' null,
    constraint notification_category_id_fk
        foreign key (categoryId) references category (id)
            on delete cascade
);

create table notification_read
(
    username        varchar(128) not null,
    notification_id int          not null,
    primary key (username, notification_id),
    constraint notification_read_notification_id_fk
        foreign key (notification_id) references notification (id)
            on delete cascade
);

create table notification_subscriptions
(
    email      varchar(128) not null,
    categoryId int          not null,
    primary key (email, categoryId),
    constraint notification_subscriptions_category_id_fk
        foreign key (categoryId) references category (id)
            on delete cascade
);

create table email_verifications
(
    email    varchar(512)     not null
        primary key,
    verified bit default b'0' null,
    token    text             null
);
