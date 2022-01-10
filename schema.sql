create table pci_vendor
(
    id     integer
        constraint pci_vendor_pk
            primary key,
    name   text not null,
    wrong_id integer default 0 not null
);

create table pci_dev
(
    id         integer
        constraint pci_dev_pk
            primary key,
    vendorId   integer not null
        references pci_vendor,
    deviceName text not null
);

create table pci_sub_dev
(
    parent_vendor integer
        references pci_vendor,
    subvendor   integer
    constraint pci_subdev_pk
            primary key,
    subdevice   integer,
    subsystem_name text
);
